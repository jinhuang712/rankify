"""Ties the engine to the store. The CLI, the terminal UI and the tests all go through here."""

import itertools
import json
import re
import secrets
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
from time import perf_counter

import numpy as np

from rankify import store
from rankify.engine import ENGINE_VERSION, stop
from rankify.engine.baselines import (
    History,
    elo_close_pair,
    elo_ratings,
    ford_johnson_pair,
    glicko2_ratings,
    insertion_sort,
    just_sort_it_pair,
    openskill_ratings,
    trueskill_ratings,
)
from rankify.engine.calibration import JudgeProfile, estimate_profile
from rankify.engine.fit import fit_pairs, fit_pairs_learning_sigma, initial_x
from rankify.engine.forecast import FORECAST_NAME, Habits, forecast_rounds
from rankify.engine.model import A_WINS, B_WINS, TIE, Choices, Pairs, Prior
from rankify.engine.planner import (
    ALL_KINDS,
    MIXED_PLANNER_NAME,
    PAIRS_ONLY,
    PLANNER_NAME,
    VARIANTS,
    Timing,
    derive_seed,
    plan_round,
    random_pair,
)
from rankify.engine.stats import SCORE_SCALE, summarize
from rankify.store import Transaction

MODES = ("quick", "stable", "exact")
# pairs is the default: mixed rounds (pairs, "pick the best" and "put in order") did not save
# time in the Phase 3 benchmark (goal G3), so they stay behind `new --rounds mixed`.
ROUNDS = ("pairs", "mixed")
# "rankify" is the product. The others exist so rankify can be benchmarked against them
# through exactly the same commands.
METHODS = (
    "rankify",
    # rating systems built for human judges
    "elo",
    "elo-close",
    "glicko2",
    "trueskill",
    "openskill",
    "arena",
    # reference lines: sorts that assume a consistent judge
    "just-sort-it",
    "insertion-sort",
    "ford-johnson",
)
# ranking comes from our Bradley-Terry fit
_FITTED = ("rankify", "arena", "just-sort-it", "ford-johnson")
# learn the prior width; arena keeps a flat prior
_LEARNS_SIGMA = ("rankify", "just-sort-it", "ford-johnson")
_RANDOM_PAIRS = ("elo", "glicko2", "trueskill", "openskill", "arena")
_RATED = {
    "glicko2": glicko2_ratings,
    "trueskill": trueskill_ratings,
    "openskill": openskill_ratings,
}
ARENA_SIGMA = 10.0  # Chatbot Arena fits Bradley-Terry with almost no prior
CALIBRATION_REPEATS = 0.15  # share of calibration rounds that repeat an earlier pair
_REPEAT_GAP = 8  # never repeat one of the last few pairs, so the judge can't just remember it
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class RankifyError(Exception):
    """A problem the user can fix, reported as a plain message."""


class NothingToAsk(RankifyError):
    """The method has no question left: its ranking is final."""


@dataclass(frozen=True)
class ShownItem:
    n: int  # the number the judge types
    id: int
    name: str


@dataclass(frozen=True)
class RoundView:
    list: str
    round: int
    kind: str
    prompt: str
    items: list[ShownItem]


@dataclass(frozen=True)
class RankedItem:
    rank: int
    id: int
    name: str
    score: float | None
    confidence: float | None
    could_be: tuple[int, int] | None


@dataclass(frozen=True)
class RankingView:
    list: str
    title: str
    mode: str
    method: str
    answers: int
    items: list[RankedItem]
    position_bias: float | None  # fitted first-slot bonus, in Score points
    tie_weight: float | None  # Davidson nu
    target_reached: bool | None = None  # None for methods without Confidence
    sigma: float | None = None  # learned prior width

    def as_dict(self) -> dict:
        return asdict(self)


TIER_LEVEL = stop.STABLE_LEVEL  # a new tier starts below a gap this confident


def tiers(items: list["RankedItem"]) -> list[list["RankedItem"]] | None:
    """The ranking in tiers: a new tier starts wherever the item above is confidently better
    (Confidence at least TIER_LEVEL, as Stable mode asks of its tiers). Inside a tier the
    order is not settled yet. None for methods without Confidence."""
    if any(i.confidence is None for i in items[:-1]):
        return None
    out: list[list[RankedItem]] = []
    for k, item in enumerate(items):
        if k == 0 or items[k - 1].confidence >= TIER_LEVEL:
            out.append([])
        out[-1].append(item)
    return out


@dataclass(frozen=True)
class RebuildView:
    list: str
    engine_before: str | None  # the engine that made the latest fit, if any
    engine_now: str
    answers: int
    moved: list[tuple[str, int, int]]  # (item, rank before, rank now)
    forecasts_dropped: int

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ListSummary:
    list: str
    title: str
    mode: str
    method: str
    items: int
    answers: int


@dataclass(frozen=True)
class Refit:
    rows: list[store.FitItemRow]  # ranked items, best first
    params: dict
    iterations: int
    x: np.ndarray | None  # warm-start state, for fitted methods
    item_ids: list[int]
    upto_round_id: int | None
    n_answers: int
    ms: float
    theta: np.ndarray | None = None  # scores and covariance, for methods that have them
    theta_cov: np.ndarray | None = None
    # (position, reach_lo, reach_hi), best first: the ranges the stopping rules use
    ranks: list[tuple[int, int, int]] | None = None
    history: list = field(default_factory=list)  # pair answers, as item positions
    set_rounds: list = field(default_factory=list)  # answered pick and rank rounds
    unanswered_sets: list = field(default_factory=list)  # sets the judge couldn't decide


@dataclass(frozen=True)
class ForecastView:
    """Rounds left until the mode's target, as a 10–90% range around the median. When too
    many draws need more than the cap, the median is unknown and ``at_least`` gives a floor."""

    list: str
    mode: str
    median: int | None
    low: int | None
    high: int | None
    at_least: int | None
    draws: int
    ms: float

    def as_dict(self) -> dict:
        return {
            "median": self.median,
            "low": self.low,
            "high": self.high,
            "at_least": self.at_least,
            "updating": False,
        }

    def text(self) -> str:
        if self.median is None:
            return f"at least {self.at_least} rounds left"
        if self.median == 0:
            return "no rounds left"
        if self.high is None:
            return f"about {self.median} rounds left ({self.low} or more)"
        return f"about {self.median} rounds left ({self.low}–{self.high})"


@dataclass(frozen=True)
class WhyView:
    list: str
    round: int
    mode: str
    reason: str
    in_play: int
    chosen: dict | None
    candidates: list[dict]
    timing: dict


class Rankify:
    def __init__(self, conn, judge: str = "me"):
        self.conn = conn
        self.judge = judge
        self._fits: dict[int, tuple[tuple, Refit]] = {}  # list id -> (state key, its fit)

    # ------------------------------------------------------------ lists and items

    def create_list(
        self,
        slug: str,
        title: str,
        items: Sequence[str] = (),
        *,
        mode: str = "stable",
        method: str = "rankify",
        seed: int | None = None,
        calibrate: bool = False,
        rounds: str = "pairs",
        planner: str = "time",
    ) -> None:
        """Make a list. ``calibrate`` mixes in repeats of earlier pairs, with the sides swapped,
        so ``calibrate()`` can measure how consistent the judge is. ``rounds`` is "pairs" or
        "mixed" (pairs, picks and rankings); other methods and calibration ask pairs."""
        if not _SLUG.match(slug):
            raise RankifyError(
                "a list name uses lowercase letters, digits and dashes, like 'nba-goat'"
            )
        if mode not in MODES:
            raise RankifyError(f"mode must be one of: {', '.join(MODES)}")
        if method not in METHODS:
            raise RankifyError(f"method must be one of: {', '.join(METHODS)}")
        if rounds not in ROUNDS:
            raise RankifyError(f"rounds must be one of: {', '.join(ROUNDS)}")
        if planner not in VARIANTS:
            raise RankifyError(f"planner must be one of: {', '.join(VARIANTS)}")
        if planner != "time" and (method != "rankify" or rounds != "pairs" or calibrate):
            raise RankifyError("planner variants are for benchmarking rankify on pairs")
        if store.get_list(self.conn, slug):
            raise RankifyError(f"list '{slug}' already exists")
        names = _clean_names(items)
        settings = {
            "mode": mode,
            "method": method,
            "seed": secrets.randbits(62) if seed is None else int(seed),
            "prior": asdict(Prior(sigma=ARENA_SIGMA) if method == "arena" else Prior()),
            "learn_sigma": method in _LEARNS_SIGMA,
            "rounds": rounds if method == "rankify" and not calibrate else "pairs",
        }
        if planner != "time":
            settings["planner"] = planner
        if calibrate:
            if method != "rankify":
                raise RankifyError("calibration lists use the rankify method")
            settings["repeat_share"] = CALIBRATION_REPEATS
        with Transaction(self.conn):
            list_id = store.insert_list(self.conn, slug, title, settings)
            for name in names:
                store.insert_item(self.conn, list_id, name)
            store.log(
                self.conn,
                "info",
                "list.created",
                {"list": slug, "items": len(names), "method": method},
            )
            self._refit(self._list(slug))

    def add_item(self, slug: str, name: str, note: str | None = None) -> None:
        lst = self._list(slug)
        (name,) = _clean_names([name])
        with Transaction(self.conn):
            self._check_items_can_change(lst)
            if any(
                it.name == name and it.removed_at is None for it in store.items(self.conn, lst.id)
            ):
                raise RankifyError(f"'{name}' is already in '{slug}'")
            store.insert_item(self.conn, lst.id, name, note)
            self._refit(lst)

    def remove_item(self, slug: str, name: str) -> None:
        lst = self._list(slug)
        with Transaction(self.conn):
            self._check_items_can_change(lst)
            item = self._active_item(lst, name)
            store.mark_removed(self.conn, item.id)
            self._refit(lst)

    def lists(self) -> list[ListSummary]:
        out = []
        for lst in store.all_lists(self.conn):
            active = [it for it in store.items(self.conn, lst.id) if it.removed_at is None]
            out.append(
                ListSummary(
                    lst.slug,
                    lst.title,
                    lst.settings["mode"],
                    _method(lst),
                    len(active),
                    len(store.effective_rounds(self.conn, lst.id)),
                )
            )
        return out

    # ------------------------------------------------------------ rounds

    def next_round(self, slug: str, mode: str | None = None) -> RoundView:
        """The open round, or a new one if none is open. ``mode`` overrides the list's mode
        for this question (rankify only)."""
        lst = self._list(slug)
        mode = mode or lst.settings["mode"]
        if mode not in MODES:
            raise RankifyError(f"mode must be one of: {', '.join(MODES)}")
        with Transaction(self.conn):
            judge = store.judge_id(self.conn, self.judge)
            active = self._active_ids(lst)
            query = store.pending_query(self.conn, lst.id, judge)
            if query is None or not set(query.shown) <= set(active):
                if len(active) < 2:
                    raise RankifyError(f"'{slug}' needs at least 2 items to rank")
                seq = store.next_seq(self.conn, lst.id)
                seed = derive_seed(lst.settings["seed"], seq)
                plan, kind = None, "pair"
                if _method(lst) == "rankify" and lst.settings.get("repeat_share"):
                    # Calibration lists keep the design the calibration was validated on:
                    # random pairs, some repeated with the sides swapped.
                    repeat = self._calibration_repeat(lst, active, seed)
                    shown = repeat or random_pair(np.array(active), seed)
                    planner = "calibration-repeat" if repeat else "calibration-random"
                elif _method(lst) == "rankify":
                    plan, chosen = self._smart_plan(lst, judge, mode, seed)
                    kind, shown = chosen if chosen else ("pair", None)
                    planner = PLANNER_NAME if _pairs_only(lst) else MIXED_PLANNER_NAME
                    if lst.settings.get("planner", "time") != "time":
                        planner += f"/{lst.settings['planner']}"
                else:
                    shown, planner = self._plan(lst, active, seed), _method(lst)
                if shown is None:
                    why = plan["reason"] if plan else "the ranking is final"
                    raise NothingToAsk(f"nothing left to ask for '{slug}' ({mode}): {why}")
                query = store.insert_query(
                    self.conn, lst.id, judge, seq, kind, list(shown), seed, planner, ENGINE_VERSION
                )
                if plan is not None:
                    self._save_plan(query.id, mode, plan)
        return self._round_view(lst, query)

    def answer(
        self,
        slug: str,
        numbers: list[int] | None = None,
        *,
        cant_decide: bool = False,
        round_seq: int | None = None,
        ms: int | None = None,
    ) -> RoundView:
        """Answer the open round with the numbers as shown: the better item of a pair, the
        best item of a pick, or every item best first for a ranking (the last one may be
        left out, and "3142" works for 3 1 4 2).

        "Can't decide" on a pair is a tie. On a pick or a ranking it records that the judge
        couldn't answer, teaches the model nothing, and keeps that set from being asked again.

        ``ms`` is the answer time measured by an interactive front end. Without it, the time
        runs from when the question was issued, which includes any typing."""
        lst = self._list(slug)
        with Transaction(self.conn):
            judge = store.judge_id(self.conn, self.judge)
            query = store.pending_query(self.conn, lst.id, judge)
            if query is None:
                raise RankifyError("no round is waiting for an answer; run `rankify next` first")
            if round_seq is not None and round_seq != query.seq:
                raise RankifyError(f"round {round_seq} is not open; the open round is {query.seq}")
            if cant_decide:
                if numbers:
                    raise RankifyError("give either numbers or --cant-decide, not both")
                outcome, answer = "cant_decide", None
            else:
                outcome = "answered"
                answer = _answer_from_numbers(query.kind, numbers or [], query.shown)
            if ms is None:
                ms = int(
                    (
                        datetime.fromisoformat(store.now())
                        - datetime.fromisoformat(query.issued_at)
                    ).total_seconds()
                    * 1000
                )
            store.insert_round(
                self.conn,
                lst.id,
                judge,
                query_id=query.id,
                kind=query.kind,
                shown=query.shown,
                answer=answer,
                outcome=outcome,
                undoes=None,
                ms=ms,
                seed=query.seed,
                engine_version=ENGINE_VERSION,
            )
            self._refit(lst)
        return self._round_view(lst, query)

    def undo(self, slug: str) -> RoundView:
        """Cancel the judge's last answer and ask that round again."""
        lst = self._list(slug)
        with Transaction(self.conn):
            judge = store.judge_id(self.conn, self.judge)
            mine = [r for r in store.effective_rounds(self.conn, lst.id) if r.judge_id == judge]
            if not mine:
                raise RankifyError("nothing to undo")
            last = mine[-1]
            store.insert_round(
                self.conn,
                lst.id,
                judge,
                query_id=None,
                kind=last.kind,
                shown=last.shown,
                answer=None,
                outcome="undo",
                undoes=last.id,
                ms=None,
                seed=None,
                engine_version=ENGINE_VERSION,
            )
            seq = store.next_seq(self.conn, lst.id)
            query = store.insert_query(
                self.conn,
                lst.id,
                judge,
                seq,
                last.kind,
                last.shown,
                derive_seed(lst.settings["seed"], seq),
                "undo-repeat",
                ENGINE_VERSION,
            )
            self._refit(lst)
        return self._round_view(lst, query)

    # ------------------------------------------------------------ results

    def ranking(self, slug: str) -> RankingView:
        lst = self._list(slug)
        fit = store.latest_fit(self.conn, lst.id)
        stale = fit is None or fit.upto_round_id != store.last_round_id(self.conn, lst.id)
        if stale or fit.engine_version != ENGINE_VERSION:
            with Transaction(self.conn):
                self._refit(lst)
            fit = store.latest_fit(self.conn, lst.id)
        names = {it.id: it.name for it in store.items(self.conn, lst.id)}
        targets = fit.params.get("targets")
        return RankingView(
            list=lst.slug,
            title=lst.title,
            mode=lst.settings["mode"],
            method=_method(lst),
            answers=fit.n_answers,
            items=[
                RankedItem(
                    r.rank,
                    r.item_id,
                    names[r.item_id],
                    r.score,
                    r.confidence,
                    None if r.rank_lo is None else (r.rank_lo, r.rank_hi),
                )
                for r in fit.items
            ],
            position_bias=fit.params.get("bias_points"),
            tie_weight=fit.params.get("tie_weight"),
            target_reached=None if targets is None else targets[lst.settings["mode"]],
            sigma=fit.params.get("sigma"),
        )

    def why(self, slug: str, round_seq: int) -> WhyView:
        """Why the planner asked a round: the candidates it weighed and what it expected."""
        lst = self._list(slug)
        plan = store.plan_for_round(self.conn, lst.id, round_seq)
        if plan is None:
            raise RankifyError(
                f"round {round_seq} of '{slug}' has no saved plan (asked by another method, "
                "a calibration repeat, an undo, or it doesn't exist)"
            )
        names = {it.id: it.name for it in store.items(self.conn, lst.id)}

        def named(c: dict) -> dict:
            if "items" not in c:  # saved by a pairs-only engine (0.2)
                c = c | {"kind": "pair", "items": [c["first"], c["second"]]}
            c = c | {"names": [names[i] for i in c["items"]]}
            if c["kind"] == "pair":
                c |= {"first_name": names[c["first"]], "second_name": names[c["second"]]}
            return c

        return WhyView(
            list=lst.slug,
            round=plan["round"],
            mode=plan["mode"],
            reason=plan["reason"],
            in_play=plan["in_play"],
            chosen=None if plan["chosen"] is None else named(plan["chosen"]),
            candidates=[named(c) for c in plan["candidates"]],
            timing=plan["timing"],
        )

    def forecast(self, slug: str, mode: str | None = None) -> ForecastView | None:
        """Rounds left until ``mode``'s target (the list's mode by default), from the answers
        each pair it needs will take. A forecast for the same answers, items and mode is reused.
        ``None`` for methods and lists the planner doesn't drive."""
        lst = self._list(slug)
        mode = mode or lst.settings["mode"]
        if mode not in MODES:
            raise RankifyError(f"mode must be one of: {', '.join(MODES)}")
        if _method(lst) != "rankify" or lst.settings.get("repeat_share"):
            return None
        upto = store.last_round_id(self.conn, lst.id)
        active = self._active_ids(lst)

        def view(f) -> ForecastView:
            return ForecastView(
                lst.slug,
                mode,
                f.median,
                f.low,
                f.high,
                f.at_least,
                f.draws,
                f.ms,
            )

        # The judge's own times and habits go into the forecast.
        version = f"{ENGINE_VERSION}/{FORECAST_NAME}/{self.judge}"
        saved = store.latest_forecast(self.conn, lst.id, upto, active, mode, version)
        if saved is not None:
            return view(saved)
        args = self.forecast_inputs(slug, mode)
        assert args is not None
        f = forecast_rounds(**args)
        with Transaction(self.conn):
            store.insert_forecast(self.conn, lst.id, upto, active, mode, f, version)
        return view(f)

    def forecast_inputs(self, slug: str, mode: str | None = None) -> dict | None:
        """Everything ``forecast_rounds`` needs, taken from the list as it is now, so the
        forecast can run on another thread without touching the database."""
        lst = self._list(slug)
        if _method(lst) != "rankify" or lst.settings.get("repeat_share"):
            return None
        r = self._current(lst)
        judge = store.judge_id(self.conn, self.judge)
        timing = Timing.fit(
            store.timing_samples(self.conn, lst.id, judge),
            store.set_timing_samples(self.conn, lst.id, judge),
        )
        return {
            "mode": mode or lst.settings["mode"],
            "theta": r.theta,
            "cov": r.theta_cov,
            "active": [p for p, _, _ in r.ranks],
            "looks": _looks(r),
            "seed": derive_seed(lst.settings["seed"], r.upto_round_id or 0, 3),
            "timing": timing,
            "kinds": PAIRS_ONLY if _pairs_only(lst) else ALL_KINDS,
            "habits": Habits(
                tie=float(np.exp(r.x[-1])),  # the fit's Davidson weight
                sharpness=_sharpness(
                    store.answers_with_prior_fit(self.conn, lst.id, judge, SHARPNESS_ANSWERS)
                ),
            ),
            **_sittings(store.effective_rounds(self.conn, lst.id), judge),
            "sigma": r.params.get("sigma"),
        }

    def calibrate(self, slugs: str | Sequence[str]) -> JudgeProfile:
        """Estimate how this judge answers, from their rounds on one or more lists. Pairs
        measure the judge's accuracy, habits and pace; timed picks and orderings measure how
        long sets take next to that pace."""
        slugs = [slugs] if isinstance(slugs, str) else list(slugs)
        judge = store.judge_id(self.conn, self.judge)
        a, b, y, seconds, sets = [], [], [], [], []
        offset, planned = 0, False
        for slug in slugs:
            lst = self._list(slug)
            planned |= not lst.settings.get("repeat_share")
            ids = [it.id for it in store.items(self.conn, lst.id)]
            pos = {iid: offset + k for k, iid in enumerate(ids)}
            theta = None
            for r in store.effective_rounds(self.conn, lst.id):
                if r.judge_id != judge:
                    continue
                if r.kind == "pair":
                    first, second = r.shown
                    a.append(pos[first])
                    b.append(pos[second])
                    if r.outcome == "cant_decide":
                        y.append(TIE)
                    else:
                        y.append(A_WINS if r.answer[0] == first else B_WINS)
                    seconds.append(None if r.ms is None else r.ms / 1000.0)
                elif r.outcome == "answered" and r.ms is not None:
                    if theta is None:
                        theta = self._current(lst).theta
                    if theta is None:
                        continue
                    order = r.answer + [i for i in r.shown if i not in r.answer]
                    local = {iid: k for k, iid in enumerate(ids)}
                    scores = [float(theta[local[i]]) for i in order]
                    sets.append((r.kind, scores, r.ms / 1000.0))
            offset += len(ids)
        if len(y) < 20:
            raise RankifyError(f"need at least 20 pair answers from '{self.judge}' to calibrate")
        return estimate_profile(offset, a, b, y, seconds, set_rounds=sets, planned=planned)

    def export(self, slug: str) -> list[dict]:
        """The list as plain records: a header, every item, then every round, undos and
        can't-decides included. Items are numbered from 1 in the order they were added, and
        rounds refer to items and to the rounds they undo by number, so the log stands on
        its own outside this database."""
        lst = self._list(slug)
        items = store.item_log(self.conn, lst.id)
        number = {it["id"]: k for k, it in enumerate(items, start=1)}
        judges = store.judge_names(self.conn)
        rounds = store.round_log(self.conn, lst.id)
        ordinal = {r["id"]: k for k, r in enumerate(rounds, start=1)}
        out: list[dict] = [
            {
                "rankify": "export",
                "format": 1,
                "list": lst.slug,
                "title": lst.title,
                "settings": lst.settings,
                "created_at": lst.created_at,
                "engine_version": ENGINE_VERSION,
            }
        ]
        for it in items:
            out.append(
                {
                    "item": number[it["id"]],
                    "name": it["name"],
                    "note": it["note"],
                    "attributes": None
                    if it["attributes"] is None
                    else json.loads(it["attributes"]),
                    "added_at": it["added_at"],
                    "removed_at": it["removed_at"],
                }
            )
        for r in rounds:
            out.append(
                {
                    "round": ordinal[r["id"]],
                    "judge": judges[r["judge_id"]],
                    "kind": r["kind"],
                    "shown": [number[i] for i in r["shown"]],
                    "answer": None if r["answer"] is None else [number[i] for i in r["answer"]],
                    "outcome": r["outcome"],
                    "undoes": ordinal.get(r["undoes"]),
                    "ms": r["ms"],
                    "seed": r["seed"],
                    "engine_version": r["engine_version"],
                    "created_at": r["created_at"],
                }
            )
        return out

    def rebuild(self, slug: str) -> RebuildView:
        """Refit the list from its answer log alone, with this engine, and drop the saved
        forecasts. The fits made after each answer, and the planner's records, stay as they
        are: they record what rankify believed, and asked, at the time."""
        lst = self._list(slug)
        before = store.latest_fit(self.conn, lst.id)
        with Transaction(self.conn):
            dropped = store.delete_forecasts(self.conn, lst.id)
            r = self._refit(lst, warm=False)
        after = store.latest_fit(self.conn, lst.id)
        names = {it.id: it.name for it in store.items(self.conn, lst.id)}
        old = {} if before is None else {row.item_id: row.rank for row in before.items}
        moved = [
            (names[row.item_id], old[row.item_id], row.rank)
            for row in after.items
            if row.item_id in old and old[row.item_id] != row.rank
        ]
        return RebuildView(
            lst.slug,
            None if before is None else before.engine_version,
            ENGINE_VERSION,
            r.n_answers,
            moved,
            dropped,
        )

    def verify(self, slug: str) -> list[str]:
        """Rebuild the latest fit from the answer log alone and compare. Returns problems found."""
        lst = self._list(slug)
        stored = store.latest_fit(self.conn, lst.id)
        if stored is None:
            return ["no stored fit"]
        if stored.engine_version != ENGINE_VERSION:
            return [
                (
                    f"the stored fit was made by engine {stored.engine_version}, this is "
                    f"{ENGINE_VERSION}; run `rankify rebuild {slug}`, then verify again"
                )
            ]
        problems = []
        last = store.last_round_id(self.conn, lst.id)
        if stored.upto_round_id != last:
            problems.append(
                f"stored fit covers rounds up to {stored.upto_round_id}, log is at {last}"
            )
        fresh = self._compute(lst, warm=False)
        if stored.n_answers != fresh.n_answers:
            problems.append(f"answer count: stored {stored.n_answers}, log {fresh.n_answers}")
        by_id = {r.item_id: r for r in stored.items}
        if sorted(by_id) != sorted(r.item_id for r in fresh.rows):
            problems.append("ranked items differ between the stored fit and the log")
            return problems
        for f in fresh.rows:
            s = by_id[f.item_id]
            checks = [
                ("theta", _close(s.theta, f.theta, 1e-6)),
                ("score", _close(s.score, f.score, 1e-4)),
                ("rank", s.rank == f.rank),
                ("could be", (s.rank_lo, s.rank_hi) == (f.rank_lo, f.rank_hi)),
                ("confidence", _close(s.confidence, f.confidence, 1e-6)),
            ]
            problems += [f"item {f.item_id}: {what} differs" for what, ok in checks if not ok]
        return problems

    # ------------------------------------------------------------ internals

    def _list(self, slug: str) -> store.ListRow:
        lst = store.get_list(self.conn, slug)
        if lst is None:
            raise RankifyError(
                f"no list named '{slug}'; create it with `rankify new {slug} \"Title\"`"
            )
        return lst

    def _active_ids(self, lst: store.ListRow) -> list[int]:
        return [it.id for it in store.items(self.conn, lst.id) if it.removed_at is None]

    def _active_item(self, lst: store.ListRow, name: str) -> store.ItemRow:
        for it in store.items(self.conn, lst.id):
            if it.name == name and it.removed_at is None:
                return it
        raise RankifyError(f"no item named '{name}' in '{lst.slug}'")

    def _check_items_can_change(self, lst: store.ListRow) -> None:
        if _method(lst) != "rankify" and store.effective_rounds(self.conn, lst.id):
            raise RankifyError(f"the {_method(lst)} method can't change items once rounds exist")

    def _round_view(self, lst: store.ListRow, query: store.QueryRow) -> RoundView:
        names = {it.id: it.name for it in store.items(self.conn, lst.id)}
        prompt = {
            "pair": "Which is better?",
            "pick": "Which is best?",
            "rank": "Put these in order, best first",
        }[query.kind]
        return RoundView(
            list=lst.slug,
            round=query.seq,
            kind=query.kind,
            prompt=prompt,
            items=[ShownItem(k + 1, iid, names[iid]) for k, iid in enumerate(query.shown)],
        )

    def _history(self, lst: store.ListRow, pos: dict[int, int], rounds=None) -> History:
        """Effective pair answers in log order, as item positions. ``rounds`` saves reading
        the log again when the caller already has it."""
        out = []
        for r in store.effective_rounds(self.conn, lst.id) if rounds is None else rounds:
            if r.kind != "pair":
                continue  # see _set_rounds
            first, second = r.shown
            if r.outcome == "cant_decide":
                y = TIE
            else:
                y = A_WINS if r.answer[0] == first else B_WINS
            out.append((pos[first], pos[second], y))
        return out

    @staticmethod
    def _set_rounds(rounds, pos: dict[int, int]) -> list[tuple[list, list]]:
        """Answered pick and rank rounds in log order: (shown, answer), as item positions."""
        return [
            ([pos[i] for i in r.shown], [pos[i] for i in r.answer])
            for r in rounds
            if r.kind != "pair" and r.outcome == "answered"
        ]

    def _calibration_repeat(
        self, lst: store.ListRow, active: list[int], seed: int
    ) -> tuple[int, int] | None:
        """On calibration lists, sometimes re-ask an earlier pair with the sides swapped."""
        share = lst.settings.get("repeat_share", 0.0)
        rng = np.random.default_rng([seed, 7])
        if not share or rng.random() >= share:
            return None
        live = set(active)
        rounds = [
            r
            for r in store.effective_rounds(self.conn, lst.id)
            if r.kind == "pair" and set(r.shown) <= live
        ]
        asked = Counter(frozenset(r.shown) for r in rounds)
        pool = [r for r in rounds[:-_REPEAT_GAP] if asked[frozenset(r.shown)] == 1]
        if len(rounds) <= _REPEAT_GAP or not pool:
            return None
        first, second = pool[int(rng.integers(len(pool)))].shown
        return second, first

    def _plan(self, lst: store.ListRow, active: list[int], seed: int) -> tuple[int, int] | None:
        """The next pair of item ids, or None when the method has nothing left to ask."""
        method = _method(lst)
        if method in _RANDOM_PAIRS:
            return random_pair(np.array(active), seed)
        ids = [it.id for it in store.items(self.conn, lst.id)]
        pos = {iid: k for k, iid in enumerate(ids)}
        history = self._history(lst, pos)
        active_pos = [pos[i] for i in active]
        sort_seed = derive_seed(lst.settings["seed"], 0)
        if method == "elo-close":
            a, b = elo_close_pair(np.array(active_pos), len(ids), history, seed)
        elif method == "insertion-sort":
            state = insertion_sort(active_pos, history, sort_seed)
            if state.next_pair is None:
                return None
            a, b = state.next_pair
        elif method == "ford-johnson":
            pair = ford_johnson_pair(active_pos, history, sort_seed)
            if pair is None:
                return None
            a, b = pair
        else:
            a, b = just_sort_it_pair(active_pos, history, sort_seed)
        return ids[a], ids[b]

    @staticmethod
    def _sorted_rows(lst, rows, active, history, ids, params) -> list:
        """Ford-Johnson, once its sort is done, shows the sort's own order: it treats every
        answer as final, and our fit can order two items it never compared differently.
        Confidence and Could be come from the fit, so they are left out then."""
        order: list[int] = []
        if ford_johnson_pair(active, history, derive_seed(lst.settings["seed"], 0), order):
            return rows
        params["finished"] = True
        rank = {ids[p]: r for r, p in enumerate(order, start=1)}
        out = [
            replace(row, rank=rank[row.item_id], rank_lo=None, rank_hi=None, confidence=None)
            for row in rows
        ]
        return sorted(out, key=lambda row: row.rank)

    def _compute(self, lst: store.ListRow, *, warm: bool) -> Refit:
        t0 = perf_counter()
        method = _method(lst)
        items = store.items(self.conn, lst.id)
        ids = [it.id for it in items]
        pos = {iid: k for k, iid in enumerate(ids)}
        rounds = store.effective_rounds(self.conn, lst.id)
        history = self._history(lst, pos, rounds)
        set_rounds = self._set_rounds(rounds, pos)
        unanswered_sets = [
            frozenset(pos[i] for i in r.shown)
            for r in rounds
            if r.kind != "pair" and r.outcome == "cant_decide"
        ]
        active = [k for k, it in enumerate(items) if it.removed_at is None]
        upto = store.last_round_id(self.conn, lst.id)
        x, iterations, params = None, 0, {}
        theta = cov = ranks = None

        if method in _FITTED:
            pairs = Pairs.of(*zip(*history, strict=True)) if history else Pairs.of([], [], [])
            choices = Choices.of(set_rounds)
            prior = Prior(**lst.settings["prior"])
            x0 = self._warm_start(lst, ids, prior) if warm else None
            if lst.settings.get("learn_sigma", method in _LEARNS_SIGMA):
                sigma0 = self._last_sigma(lst) if warm else None
                fit = fit_pairs_learning_sigma(
                    len(ids), pairs, prior, x0=x0, sigma0=sigma0, choices=choices
                )
            else:
                fit = fit_pairs(len(ids), pairs, prior, x0=x0, choices=choices)
            theta, cov = fit.theta, fit.theta_cov
            x, iterations = fit.x, fit.iterations
            params = {
                "bias_points": fit.bias * SCORE_SCALE,
                "tie_weight": fit.tie,
                "sigma": fit.sigma or prior.sigma,
            }
        elif method in _RATED:
            theta, sd = _RATED[method](len(ids), history)
            cov = np.diag(sd**2)

        if theta is not None:
            stats = summarize(
                theta,
                cov,
                np.array(active, dtype=np.int64),
                seed=derive_seed(lst.settings["seed"], upto or 0, 1),
            )
            rows = [
                store.FitItemRow(
                    ids[s.index], s.theta, s.sd, s.score, s.rank, s.rank_lo, s.rank_hi, s.confidence
                )
                for s in stats
            ]
            ranks = [(s.index, s.reach_lo, s.reach_hi) for s in stats]  # for stopping
            nb = stop.neighbours(theta, cov, [s.index for s in stats])
            params["targets"] = {m: stop.target_reached(m, nb, ranks) for m in MODES}
            if method == "ford-johnson":
                rows = self._sorted_rows(lst, rows, active, history, ids, params)
        elif method in ("elo", "elo-close"):
            ratings = elo_ratings(len(ids), history)
            order = sorted(active, key=lambda k: (-ratings[k], k))
            rows = [
                store.FitItemRow(ids[k], None, None, float(ratings[k]), r + 1, None, None, None)
                for r, k in enumerate(order)
            ]
        else:  # insertion-sort
            state = insertion_sort(active, history, derive_seed(lst.settings["seed"], 0))
            order = state.ranked + state.unranked
            rows = [
                store.FitItemRow(ids[k], None, None, None, r + 1, None, None, None)
                for r, k in enumerate(order)
            ]
            params = {"finished": state.next_pair is None, "unranked": len(state.unranked)}
        return Refit(
            rows,
            params,
            iterations,
            x,
            ids,
            upto,
            len(history) + len(set_rounds),
            (perf_counter() - t0) * 1000,
            theta=theta,
            theta_cov=cov,
            ranks=ranks,
            history=history,
            set_rounds=set_rounds,
            unanswered_sets=unanswered_sets,
        )

    def _smart_plan(
        self, lst: store.ListRow, judge: int, mode: str, seed: int
    ) -> tuple[dict, tuple[str, list[int]] | None]:
        """rankify's planner: the round worth the most per second as (kind, item ids in
        display order), or None to stop."""
        r = self._current(lst)
        timing = Timing.fit(
            store.timing_samples(self.conn, lst.id, judge),
            store.set_timing_samples(self.conn, lst.id, judge),
        )
        ids = r.item_ids
        looks = _looks(r)
        avoid = frozenset(r.unanswered_sets)
        kinds = PAIRS_ONLY if _pairs_only(lst) else ALL_KINDS
        variant = lst.settings.get("planner", "time")
        plan = plan_round(
            mode, r.theta, r.theta_cov, r.ranks, timing, seed, looks, kinds, avoid, variant
        )

        def describe(c) -> dict:
            out = {
                "kind": c.kind,
                "items": [ids[p] for p in c.items],
                "gain": c.gain,
                "seconds": c.seconds,
                "value": c.value,
            }
            if c.kind == "pair":
                out |= {
                    "first": ids[c.first],
                    "second": ids[c.second],
                    "confidence": c.confidence,
                    "closeness": c.closeness,
                }
            return out

        record = {
            "reason": plan.reason,
            "in_play": plan.in_play,
            "chosen": None if plan.chosen is None else describe(plan.chosen),
            "closeness": None if plan.chosen is None else plan.chosen.closeness,
            "candidates": [describe(c) for c in plan.candidates],
            "timing": {
                "base": timing.base,
                "close": timing.close,
                "samples": timing.samples,
                "typical": timing.typical,
                "sets": {
                    f"{kind} {size}": timing.set_seconds(kind, size)
                    for kind in ("pick", "rank")
                    for size in range(3, 6)
                },
                "set_samples": {f"{k} {s}": count for k, s, _, count in timing.sets},
            },
        }
        if plan.chosen is None:
            return record, None
        return record, (plan.chosen.kind, [ids[p] for p in plan.chosen.items])

    def _save_plan(self, query_id: int, mode: str, record: dict) -> None:
        store.insert_plan(
            self.conn,
            query_id,
            mode=mode,
            reason=record["reason"],
            in_play=record["in_play"],
            closeness=record["closeness"],
            chosen=record["chosen"],
            candidates=record["candidates"],
            timing=record["timing"],
        )

    def _last_sigma(self, lst: store.ListRow) -> float | None:
        fit = store.latest_fit(self.conn, lst.id)
        return None if fit is None else fit.params.get("sigma")

    def _state_key(self, lst: store.ListRow) -> tuple:
        """Everything a fit depends on that can change: the answer log and the items."""
        items = tuple((it.id, it.removed_at is None) for it in store.items(self.conn, lst.id))
        return store.last_round_id(self.conn, lst.id), items

    def _current(self, lst: store.ListRow) -> Refit:
        """The fit of the list as it is now. Reuses the last refit when nothing has changed
        since, so asking the next round right after an answer doesn't fit twice."""
        key = self._state_key(lst)
        cached = self._fits.get(lst.id)
        if cached is not None and cached[0] == key:
            return cached[1]
        r = self._compute(lst, warm=True)
        self._fits[lst.id] = (key, r)
        return r

    def _refit(self, lst: store.ListRow, warm: bool = True) -> Refit:
        r = self._compute(lst, warm=warm)
        self._fits[lst.id] = (self._state_key(lst), r)
        store.insert_fit(
            self.conn,
            lst.id,
            upto_round_id=r.upto_round_id,
            n_answers=r.n_answers,
            engine_version=ENGINE_VERSION,
            iterations=r.iterations,
            ms=r.ms,
            params=r.params,
            item_rows=r.rows,
            item_ids=r.item_ids,
            x_bytes=None if r.x is None else r.x.astype(np.float64).tobytes(),
        )
        return r

    def _warm_start(self, lst: store.ListRow, item_ids: list[int], prior: Prior) -> np.ndarray:
        n = len(item_ids)
        x0 = initial_x(n, prior)
        state = store.fit_state(self.conn, lst.id)
        if state is None:
            return x0
        old_ids, raw = state
        old_x = np.frombuffer(raw, dtype=np.float64)
        old_pos = {iid: k for k, iid in enumerate(old_ids)}
        for k, iid in enumerate(item_ids):
            if iid in old_pos:
                x0[k] = old_x[old_pos[iid]]
        x0[n:] = old_x[len(old_ids) :]
        return x0


def _method(lst: store.ListRow) -> str:
    return lst.settings.get("method", "rankify")


def _looks(r: Refit) -> Counter:
    """How many answered rounds each item position has been shown in."""
    looks: Counter = Counter()
    for a, b, _ in r.history:
        looks[a] += 1
        looks[b] += 1
    for shown, _ in r.set_rounds:
        looks.update(shown)
    return looks


SITTING_GAP = timedelta(minutes=30)  # a longer pause starts a new sitting
SHARPNESS_ANSWERS = 200  # the judge's latest answers that measure their sharpness
SHARPNESS_SD = 0.5  # prior sd of its log: about 1, unless the answers say otherwise
_SHARPNESS_GRID = np.exp(np.linspace(np.log(0.25), np.log(8.0), 57))


def _sharpness(answers) -> float:
    """How much more decisive the judge is than the model expects: a calibration slope (Cox
    1958), from what rankify expected just before each answer. A judge the model describes
    well comes out near 1; one who never contradicts themself, far above it.

    Each answer is read as comparisons: a pair as one; an ordering as every pair in it,
    since under Plackett–Luce the chance that a comes before b anywhere in the order is the
    pair's own chance (neighbours alone would read a model-following judge as about 0.7);
    a pick as the chosen item against each other one. Sets are weighted to count as as
    many choices as they hold. With a sharpness k, the chance that w beats l, given that rankify thought
    their gap was mu with variance v, is about sigmoid(k mu / sqrt(1 + pi k² v / 8))
    (MacKay 1992), so an unsure expectation says little either way."""
    mu, var, weight = [], [], []
    for kind, shown, answer, before in answers:
        if kind == "pair":
            won = answer[0]
            comparisons = [(won, next(i for i in shown if i != won))]
            w = 1.0
        elif kind == "pick":
            comparisons = [(answer[0], i) for i in shown if i != answer[0]]
            w = 1.0 / len(comparisons)
        else:
            comparisons = list(itertools.combinations(answer, 2))
            w = 2.0 / len(answer)  # k - 1 choices' worth
        for a, b in comparisons:
            mu.append(before[a][0] - before[b][0])
            var.append(before[a][1] ** 2 + before[b][1] ** 2)
            weight.append(w)
    if not mu:
        return 1.0
    m, v, w = (np.array(x)[None, :] for x in (mu, var, weight))
    k = _SHARPNESS_GRID[:, None]
    z = k * m / np.sqrt(1.0 + np.pi * k**2 * v / 8.0)
    loglik = -(w * np.logaddexp(0.0, -z)).sum(axis=1)
    prior = -0.5 * (np.log(_SHARPNESS_GRID) / SHARPNESS_SD) ** 2
    return float(_SHARPNESS_GRID[np.argmax(loglik + prior)])


def _sittings(rounds: list[store.RoundRow], judge: int, at: datetime | None = None) -> dict:
    """Fatigue builds up within a sitting and resets between them. Returns ``effort``, the
    calls this judge has made in the sitting under way (0 if their last answer was more than
    SITTING_GAP ago), and ``past_efforts``, how far into its sitting each call behind the
    fit was made, by any judge. A pair is one call, and a set of k items k - 1."""
    at = at or datetime.now(UTC)
    past: list[int] = []
    last: dict[int, tuple[datetime, int]] = {}  # judge -> (last answer, calls this sitting)
    for r in rounds:
        t = datetime.fromisoformat(r.created_at) if r.created_at else at
        before = last.get(r.judge_id)
        done = 0 if before is None or t - before[0] > SITTING_GAP else before[1]
        calls = max(len(r.shown) - 1, 1)
        past.extend(range(done, done + calls))
        last[r.judge_id] = (t, done + calls)
    mine = last.get(judge)
    effort = mine[1] if mine is not None and at - mine[0] <= SITTING_GAP else 0
    return {"effort": effort, "past_efforts": past}


def _pairs_only(lst: store.ListRow) -> bool:
    return lst.settings.get("rounds", "pairs") == "pairs"


def _close(a: float | None, b: float | None, tol: float) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def _clean_names(names) -> list[str]:
    out, seen = [], set()
    for raw in names:
        name = " ".join(str(raw).split())
        if not name:
            continue
        if name in seen:
            raise RankifyError(f"'{name}' appears twice")
        seen.add(name)
        out.append(name)
    return out


def _answer_from_numbers(kind: str, numbers: list[int], shown: list[int]) -> list[int]:
    """Item ids from the numbers the judge typed: the best one for a pick, else best first."""
    k = len(shown)
    if kind == "rank" and len(numbers) == 1 and numbers[0] > k:
        numbers = [int(c) for c in str(numbers[0])]  # "3142" for 3 1 4 2
    if kind == "pick":
        if len(numbers) != 1 or not 1 <= numbers[0] <= k:
            raise RankifyError(f"give the number of the best item, 1 to {k}, or --cant-decide")
        return [shown[numbers[0] - 1]]
    return _order_from_numbers(numbers, shown)


def _order_from_numbers(numbers: list[int], shown: list[int]) -> list[int]:
    """Item ids best first, from the numbers the judge typed."""
    k = len(shown)
    if not numbers:
        what = "the better item" if k == 2 else "the items in order, best first"
        raise RankifyError(f"give the number of {what}, or --cant-decide")
    if any(not 1 <= x <= k for x in numbers) or len(set(numbers)) != len(numbers):
        raise RankifyError(f"use each number from 1 to {k} at most once")
    if len(numbers) == k - 1:  # the last one is implied
        numbers = numbers + [next(x for x in range(1, k + 1) if x not in numbers)]
    if len(numbers) != k:
        raise RankifyError(f"give all {k} numbers in order, best first")
    return [shown[x - 1] for x in numbers]
