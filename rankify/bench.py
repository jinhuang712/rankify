"""Benchmark rankify against rating systems built for human judges, through the CLI.

The protocol (see EXPERIMENT.md):

1. Draw hidden scores for N items: a few clear favourites and a crowded middle.
2. For each method, make a fresh list with ``rankify new --method <method>``.
3. Each round, ``rankify next --json`` asks a question. A simulated judge compares the two
   items' hidden scores the way a person would (noisy, slower on close calls, sometimes
   unsure) and answers with ``rankify answer --round`` or ``--cant-decide``. Then
   ``rankify show --json`` records the method's current ranking.
4. Stop at the round budget, or when the method has nothing left to ask (exit code 3).

Every method goes through the same commands. Calls run in-process through Typer's test
runner, which is the real CLI code path without process start-up. A separate sample
times real subprocess calls.
"""

import itertools
import json
import math
import os
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist

import numpy as np

from rankify.engine.judge import HumanParams, human_answer

RATING_SYSTEMS = ("elo", "elo-close", "glicko2", "trueskill", "openskill", "arena")
REFERENCE = ("just-sort-it", "insertion-sort")
DEFAULT_METHODS = ("rankify", *RATING_SYSTEMS, *REFERENCE)
JUDGES = ("human", "perfect", "noisy")
DEFAULT_JUDGES = ("human", "perfect")
TARGETS = ("quick", "stable", "exact")
CONFIRM = 10  # a target counts as reached once it has held for this many more rounds
ONLINE = ("elo", "glicko2", "trueskill", "openskill")  # update one match at a time
_PHI = NormalDist()


# ---------------------------------------------------------------- the judges


HUMAN = HumanParams()  # the guessed person; `rankify calibrate` measures a real one
SCORE_SPREAD = 1.5  # hidden scores = spread x Student-t(3): a few far out, a crowded middle
# Pairs closer than this are near-ties the human judge gets right under 55% of the time.
# Targets ignore swaps between such pairs, the same way rankify shows them as ties.
TIE_MARGIN = math.sqrt(2.0) * HUMAN.noise * _PHI.inv_cdf(0.55)


class Judge:
    """Answers from hidden scores. ``kind`` is human, perfect or noisy."""

    def __init__(
        self,
        theta: dict[str, float],
        kind: str,
        rng: np.random.Generator,
        params: HumanParams = HUMAN,
    ):
        self.theta, self.kind, self.rng, self.p = theta, kind, rng, params

    def answer(self, shown: list[str], round_no: int) -> tuple[int | None, float]:
        """(1 or 2 for the better item, or None for "can't decide"; seconds taken)."""
        p, rng = self.p, self.rng
        diff = self.theta[shown[0]] - self.theta[shown[1]]
        if self.kind == "human":
            return human_answer(p, rng, diff, round_no)
        gap = abs(diff)
        seconds = (p.base_seconds + p.close_seconds * math.exp(-gap / p.close_width)) * float(
            rng.lognormal(0.0, 0.25)
        )
        if self.kind == "perfect":
            return (1 if diff > 0 else 2), seconds
        # noisy: Bradley-Terry, the model rankify itself assumes
        p_first = 1.0 / (1.0 + math.exp(-1.702 * diff / (math.sqrt(2.0) * p.noise)))
        return (1 if rng.random() < p_first else 2), seconds


def hidden_scores(
    names: list[str], rng: np.random.Generator, spread: float = SCORE_SPREAD
) -> dict[str, float]:
    return {name: float(spread * rng.standard_t(3)) for name in names}


def list_difficulty(
    n: int, params: HumanParams = HUMAN, spread: float = SCORE_SPREAD, lists: int = 1000
) -> tuple[float, float]:
    """(median chance the human judge orders two neighbours right, share of near-ties)."""
    acc, near = [], []
    for s in range(lists):
        t = np.sort(spread * np.random.default_rng(10**6 + s).standard_t(3, n))[::-1]
        gaps = t[:-1] - t[1:]
        acc += [_PHI.cdf(g / (math.sqrt(2.0) * params.noise)) for g in gaps]
        near += list(gaps < TIE_MARGIN)
    return float(np.median(acc)), float(np.mean(near))


def load_profile(path: Path) -> dict:
    """A judge profile written by ``rankify calibrate --out``, ready for ``run_bench``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    measured = [k for k in data.get("measured", []) if k in data]
    params = {k: float(data[k]) for k in measured if k in HumanParams.__dataclass_fields__}
    guessed = [k for k in HumanParams.__dataclass_fields__ if k not in params and k != "noise"]
    return {
        "params": params,  # only what the session measured; the rest keep the guesses
        "spread": float(data["score_spread"]) if "score_spread" in measured else SCORE_SPREAD,
        "label": (
            f"from {data.get('judge', 'a judge')}'s session on '{data.get('list', '?')}' "
            f"({data.get('answers', '?')} answers, {data.get('date', 'date unknown')}). "
            f"Measured: {', '.join(measured) or 'nothing'}. Still guesses: {', '.join(guessed)}"
        ),
        "notes": list(data.get("notes", [])),
    }


def _unpack(profile: dict | None) -> tuple[HumanParams, float]:
    if not profile:
        return HUMAN, SCORE_SPREAD
    return HumanParams(**profile["params"]), profile["spread"]


# ---------------------------------------------------------------- one run


class Cli:
    """Calls the real CLI in-process and times each call."""

    def __init__(self, db: Path):
        from typer.testing import CliRunner

        from rankify.cli.main import app

        self.runner, self.app, self.db = CliRunner(), app, db
        self.ms: dict[str, list[float]] = {"next": [], "answer": [], "show": []}

    def call(self, *args: str) -> tuple[int, str]:
        t0 = time.perf_counter()
        result = self.runner.invoke(self.app, ["--db", str(self.db), *args])
        if args[0] in self.ms:
            self.ms[args[0]].append((time.perf_counter() - t0) * 1000)
        if result.exception and not isinstance(result.exception, SystemExit):
            raise result.exception
        return result.exit_code, result.stdout

    def ok(self, *args: str) -> str:
        code, out = self.call(*args)
        if code != 0:
            raise RuntimeError(f"rankify {' '.join(args)} exited with {code}: {out}")
        return out


@dataclass
class RunResult:
    method: str
    judge: str
    n: int
    seed: int
    rounds: int = 0
    finished: bool = False
    seconds: list[float] = field(default_factory=list)  # simulated human time per round
    taus: list[float] = field(default_factory=list)
    flags: dict[str, list[bool]] = field(default_factory=lambda: {t: [] for t in TARGETS})
    implied: list[bool] = field(default_factory=list)  # answer already implied by earlier ones
    repeats: list[bool] = field(default_factory=list)  # exact repeat of an earlier pair
    correct: int = 0  # answers that matched the hidden scores
    decided: int = 0  # answers that were not "can't decide"
    calibration: list[tuple[float, bool]] = field(default_factory=list)
    coverage: list[bool] = field(default_factory=list)
    reorder_changed_top: bool | None = None
    reorder_tau: float | None = None
    ms: dict[str, list[float]] = field(default_factory=dict)
    error: str | None = None  # set when the run crashed; left out of every statistic

    def reached(self, target: str) -> int | None:
        return first_confirmed(self.flags[target], self.finished)

    def minutes_to(self, target: str) -> float | None:
        r = self.reached(target)
        return None if r is None else sum(self.seconds[:r]) / 60.0


def first_confirmed(flags: list[bool], finished: bool) -> int | None:
    """First round (1-based) from which the target held for CONFIRM more rounds."""
    for r in range(len(flags)):
        if r + CONFIRM < len(flags):
            window = flags[r : r + CONFIRM + 1]
        elif finished:
            window = flags[r:]  # the method stopped; its ranking no longer changes
        else:
            return None  # not enough rounds left in the budget to confirm
        if all(window):
            return r + 1
    return None


def kendall_tau(order: list[str], theta: dict[str, float]) -> float:
    t = np.array([theta[x] for x in order])
    s = np.sign(t[:, None] - t[None, :])  # +1 where an earlier item is truly better
    iu = np.triu_indices(len(order), 1)
    return float(np.mean(s[iu]))


def targets_met(order: list[str], theta: dict[str, float], margin: float = TIE_MARGIN) -> dict:
    """Quick / Stable / Exact against the hidden scores, ignoring swaps of near-ties."""
    n = len(order)
    t = np.array([theta[x] for x in order])
    inv = np.triu(t[None, :] - t[:, None] > margin, 1)  # inv[i, j]: j shown lower, truly better
    quick = not inv[0].any() and not inv[:3, 3:].any()
    k = max(3, math.ceil(n / 4))
    stable = not inv[:k].any()
    if stable and n > k:
        true_rank = {x: r + 1 for r, x in enumerate(sorted(order, key=lambda x: -theta[x]))}

        def tier(rank: int) -> int:
            return (rank - k - 1) * 3 // (n - k)

        stable = all(
            abs(tier(true_rank[x]) - tier(i + 1)) <= 1 for i, x in enumerate(order) if i >= k
        )
    return {"quick": quick, "stable": stable, "exact": not inv.any()}


def run_one(
    method: str, judge_kind: str, n: int, seed: int, budget: int, profile: dict | None = None
) -> RunResult:
    """One hidden list, one method, through the CLI. ``method`` may name a mode, as in
    ``rankify:quick``; rankify runs once per mode so each target is measured in its mode."""
    params, spread = _unpack(profile)
    base_method, _, mode = method.partition(":")
    rng = np.random.default_rng(seed)
    names = [f"item-{k:02d}" for k in range(n)]
    theta = hidden_scores(names, rng, spread)
    true_rank = {x: r + 1 for r, x in enumerate(sorted(names, key=lambda x: -theta[x]))}
    index = {name: k for k, name in enumerate(names)}
    judge = Judge(theta, judge_kind, np.random.default_rng([seed, 1]), params)
    res = RunResult(method, judge_kind, n, seed)
    known = np.zeros((n, n), dtype=bool)  # known[w, l]: earlier answers imply w beats l
    seen: set[frozenset] = set()
    log: list[tuple[int, int, int]] = []  # (first, second, outcome) for the reorder check

    with tempfile.TemporaryDirectory() as tmp:
        db, items = Path(tmp) / "bench.db", Path(tmp) / "items.txt"
        items.write_text("\n".join(names), encoding="utf-8")
        cli = Cli(db)
        cli.ok(
            "new",
            "bench",
            "Benchmark",
            "--items",
            str(items),
            "--method",
            base_method,
            "--mode",
            mode or "stable",
            "--seed",
            str(seed),
        )
        ranking = None
        for round_no in range(budget):
            code, out = cli.call("next", "bench", "--json")
            if code == 3:
                res.finished = True
                break
            if code != 0:
                raise RuntimeError(f"next exited with {code}")
            round_ = json.loads(out)
            shown = [i["name"] for i in round_["items"]]
            pick, seconds = judge.answer(shown, round_no)
            res.seconds.append(seconds)
            a, b = index[shown[0]], index[shown[1]]
            res.repeats.append(frozenset((a, b)) in seen)
            seen.add(frozenset((a, b)))
            res.implied.append(bool(known[a, b] or known[b, a]))
            timed = ("--round", str(round_["round"]), "--ms", str(int(seconds * 1000)))
            if pick is None:
                cli.ok("answer", "bench", "--cant-decide", *timed)
                log.append((a, b, 2))
            else:
                cli.ok("answer", "bench", str(pick), *timed)
                winner, loser = (a, b) if pick == 1 else (b, a)
                log.append((a, b, 0 if pick == 1 else 1))
                res.decided += 1
                res.correct += theta[names[winner]] > theta[names[loser]]
                rows = known[:, winner].copy()
                rows[winner] = True
                cols = known[loser, :].copy()
                cols[loser] = True
                known |= np.outer(rows, cols)

            ranking = json.loads(cli.ok("show", "bench", "--json"))
            order = [i["name"] for i in ranking["items"]]
            res.rounds += 1
            res.taus.append(kendall_tau(order, theta))
            for t, ok in targets_met(order, theta).items():
                res.flags[t].append(ok)
        res.ms = cli.ms

    if ranking is not None:
        items_ = ranking["items"]
        for x, y in itertools.pairwise(items_):
            if x["confidence"] is not None:
                res.calibration.append((x["confidence"], theta[x["name"]] > theta[y["name"]]))
        for i in items_:
            if i["could_be"] is not None:
                lo, hi = i["could_be"]
                res.coverage.append(lo <= true_rank[i["name"]] <= hi)
    _reorder_check(res, log, n, np.random.default_rng([seed, 2]))
    return res


def _reorder_check(res: RunResult, log, n, rng) -> None:
    """Replay the same answers in two other orders through the method's scoring."""
    if res.method not in ("rankify:exact", *ONLINE) or len(log) < 2:
        return
    from rankify.engine import baselines
    from rankify.engine.fit import fit_pairs_learning_sigma
    from rankify.engine.model import Pairs

    def scores(order) -> np.ndarray:
        hist = [log[k] for k in order]
        if res.method == "rankify:exact":
            return fit_pairs_learning_sigma(n, Pairs.of(*zip(*hist, strict=True))).theta
        if res.method == "elo":
            return baselines.elo_ratings(n, hist)
        return getattr(baselines, f"{res.method}_ratings")(n, hist)[0]

    s1, s2 = scores(rng.permutation(len(log))), scores(rng.permutation(len(log)))
    res.reorder_changed_top = int(np.argmax(s1)) != int(np.argmax(s2))
    order1 = [str(int(k)) for k in np.argsort(-s1, kind="stable")]
    res.reorder_tau = kendall_tau(order1, {str(k): float(v) for k, v in enumerate(s2)})


def _run_task(task):
    """One run; a crash is recorded, not raised, so one bad run can't sink the benchmark."""
    try:
        return run_one(*task)
    except Exception as e:  # noqa: BLE001 - reported in full in the benchmark's report
        method, judge_kind, n, seed = task[:4]
        return RunResult(method, judge_kind, n, seed, error=f"{type(e).__name__}: {e}")


def _lower_priority() -> None:
    try:
        os.nice(10)  # yield to whatever the person is doing on this machine
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- whole benchmark

# Keep the machine cool: few workers, low priority, one numpy thread each.
DEFAULT_WORKERS = 2
_ONE_THREAD = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def run_bench(
    sizes=(10, 20),
    judges=DEFAULT_JUDGES,
    methods=DEFAULT_METHODS,
    runs: int = 20,
    budget_per_item: int = 20,
    workers: int = DEFAULT_WORKERS,
    real_cli: bool = True,
    progress=None,
    profile: dict | None = None,
    cache: Path | None = None,
) -> str:
    """Run the benchmark. ``profile`` (from ``load_profile``) replaces the guessed human judge.

    ``cache`` is a JSON-lines file of finished runs. Each run is appended as soon as it
    finishes, and runs already in the file are not run again, so an interrupted benchmark
    resumes where it stopped. Only reuse a cache with the same code.
    """
    runnable = [
        variant
        for m in methods
        for variant in ([f"rankify:{t}" for t in TARGETS] if m == "rankify" else [m])
    ]
    tasks = [
        (m, j, n, 1000 * n + s, budget_per_item * n, profile)
        for n in sizes
        for j in judges
        for s in range(runs)
        for m in runnable
    ]
    done = _load_cache(cache)
    results: list[RunResult] = [done[t[:4]] for t in tasks if t[:4] in done]
    todo = [t for t in tasks if t[:4] not in done]
    workers = max(1, min(workers, os.cpu_count() or 1))
    t0 = time.perf_counter()

    def finished(res: RunResult) -> None:
        results.append(res)
        if cache is not None and not res.error:
            with Path(cache).open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(res)) + "\n")
        if progress:
            progress(len(results), len(tasks))

    if workers == 1:
        _lower_priority()
        for task in todo:
            finished(_run_task(task))
    elif todo:
        for var in _ONE_THREAD:  # read by numpy when each worker process starts
            os.environ.setdefault(var, "1")
        with ProcessPoolExecutor(max_workers=workers, initializer=_lower_priority) as pool:
            for res in pool.map(_run_task, todo, chunksize=1):
                finished(res)
    elapsed = time.perf_counter() - t0
    failed = [r for r in results if r.error]
    results = [r for r in results if not r.error]
    real = _real_cli_sample() if real_cli else None
    text = _report(results, sizes, judges, methods, runs, budget_per_item, elapsed, real, profile)
    if failed:
        rows = [
            f"- {r.method}, {r.judge} judge, {r.n} items, seed {r.seed}: {r.error}" for r in failed
        ]
        text += "\n## Failed runs (left out of every table)\n\n" + "\n".join(rows) + "\n"
    return text


def _load_cache(cache: Path | None) -> dict[tuple, RunResult]:
    """Finished runs from a cache file, keyed by (method, judge, items, seed)."""
    if cache is None or not Path(cache).exists():
        return {}
    done = {}
    for line in Path(cache).read_text(encoding="utf-8").splitlines():
        if line.strip():
            res = RunResult(**json.loads(line))
            res.calibration = [(float(c), bool(ok)) for c, ok in res.calibration]
            done[(res.method, res.judge, res.n, res.seed)] = res
    return done


def _real_cli_sample(calls: int = 5) -> dict[str, float] | None:
    exe = Path(sys.prefix) / "bin" / "rankify"
    if not exe.exists():
        return None
    out: dict[str, list[float]] = {"next": [], "answer": [], "show": []}
    with tempfile.TemporaryDirectory() as tmp:
        items = Path(tmp) / "items.txt"
        items.write_text("\n".join(f"item-{k:02d}" for k in range(20)), encoding="utf-8")
        base = [str(exe), "--db", str(Path(tmp) / "real.db")]
        subprocess.run(
            [*base, "new", "real", "Real", "--items", str(items), "--seed", "1"],
            check=True,
            capture_output=True,
        )
        steps = (
            ("next", ["next", "real", "--json"]),
            ("answer", ["answer", "real", "1"]),
            ("show", ["show", "real", "--json"]),
        )
        for _ in range(calls):
            for name, args in steps:
                t0 = time.perf_counter()
                subprocess.run([*base, *args], check=True, capture_output=True)
                out[name].append((time.perf_counter() - t0) * 1000)
    return {k: statistics.median(v) for k, v in out.items()}


def _median_or_none(values: list[float | None]) -> float | None:
    """Median where None means "not reached"; None if half or more never reached."""
    finite = sorted(v for v in values if v is not None)
    if len(finite) * 2 <= len(values):
        return None
    return float(statistics.median(finite + [math.inf] * (len(values) - len(finite))))


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
        )
        return out.stdout.strip() + (" + uncommitted changes" if dirty.stdout.strip() else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


FEATURES = {
    "Chooses informative pairs": {
        "rankify": "yes: order information per second, weighted by the mode",
        "elo-close": "yes: close ratings",
        "just-sort-it": "yes: quicksort",
        "insertion-sort": "yes: binary search",
    },
    "Knows when it is done": {
        "rankify": "yes: confidence target, or nothing worth asking",
        "insertion-sort": "yes, but trusts every answer",
    },
    "Rounds left": {"rankify": "no (Phase 4)"},
    "Precision modes": {"rankify": "yes: quick, stable, exact"},
    "Pick / rank rounds": {"rankify": "no (Phase 3)"},
    "Confidence and Could be": {
        "rankify": "yes",
        "glicko2": "yes (from RD)",
        "trueskill": "yes (from sigma)",
        "openskill": "yes (from sigma)",
        "arena": "yes (our fit)",
        "just-sort-it": "yes (our fit)",
    },
    "Same answers, any order, same ranking": {
        "rankify": "yes",
        "arena": "yes",
        "just-sort-it": "yes",
        "insertion-sort": "n/a",
    },
}
_FEATURE_DEFAULT = {"Chooses informative pairs": "no: random pairs"}


def _report(
    results, sizes, judges, methods, runs, budget_per_item, elapsed, real, profile=None
) -> str:
    from rankify.engine import ENGINE_VERSION

    by: dict[tuple, list[RunResult]] = {}
    for r in results:
        by.setdefault((r.n, r.judge, r.method), []).append(r)
    for (n, j, m), rs in list(by.items()):
        if m == "rankify:exact":  # the longest rankify run stands for rankify in most tables
            by[(n, j, "rankify")] = rs

    def runs_for(n: int, j: str, m: str, target: str) -> list[RunResult]:
        """rankify's result for a target comes from its run in that target's mode."""
        return by[(n, j, f"rankify:{target}")] if m == "rankify" else by[(n, j, m)]

    p, spread = _unpack(profile)
    source = profile["label"] if profile else "all guesses until a real session calibrates them"
    lines = [
        "# Benchmark: rankify against rating systems for human judges",
        "",
        f"- Date: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Code: commit {_git_commit()}, engine {ENGINE_VERSION}",
        (
            f"- Setup: {', '.join(map(str, sizes))} items; judges: {', '.join(judges)}; {runs} "
            "hidden lists per setting, the same for every method; budget "
            f"{budget_per_item} rounds per item; wall time {elapsed:.0f} s."
        ),
        (
            "- Every method ran through the CLI: `new --method`, then `next`, `answer` (or "
            "`--cant-decide`) and `show` each round."
        ),
        (
            "- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees "
            f"of freedom, times {spread:.2f})."
        ),
        "",
        (
            "**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the "
            "top quarter (at least 3) in the right order, every other item within one tier of its "
            "true tier. Exact = the whole order right. Swaps between near-ties (pairs the human "
            "judge gets right under 55% of the time) don't count as errors. A target counts as "
            f"reached at the first round from which it holds for {CONFIRM} more rounds, or until "
            "the method stops asking."
        ),
        "",
        (
            "**Methods.** rankify; rating systems built for human judges (Elo, Elo with close "
            "pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and two "
            "sorts as reference lines only. The sorts assume a consistent judge, which people are "
            "not."
        ),
        "",
        "## The judges",
        "",
        (
            "**human** (the headline): perceived scores carry noise (Thurstone 1927), noise "
            "grows with fatigue, a lean toward the item shown first, occasional random answers "
            '(lapses; Wichmann & Hill 2001), "can\'t decide" on near-ties, and slower answers on '
            "close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a "
            "sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes."
        ),
        "",
        "| Judge | Answers right | Can't decide | Seconds per answer |",
        "|---|---|---|---|",
    ]
    for j in judges:
        rs = [r for r in results if r.judge == j]
        decided = sum(r.decided for r in rs)
        total = sum(r.rounds for r in rs)
        right = sum(r.correct for r in rs) / max(1, decided)
        ties = 1 - decided / max(1, total)
        secs = statistics.mean(s for r in rs for s in r.seconds)
        lines.append(f"| {j} | {right:.0%} | {ties:.0%} | {secs:.1f} |")
    difficulty = [(n, *list_difficulty(n, p, spread)) for n in sizes]
    lines += [
        "",
        "How hard the hidden lists are for the human judge, before lapses and fatigue: "
        + "; ".join(
            f"{n} items: neighbours told apart {acc:.0%} of the time (median), "
            f"{near:.0%} of neighbouring pairs are near-ties"
            for n, acc, near in difficulty
        )
        + ".",
        "",
        (
            f"Human judge settings: noise {p.noise}, fatigue +{p.fatigue:.1%} per round (up to "
            f"×{p.fatigue_cap}), first-item lean {p.first_bonus:.2f}, lapses {p.lapse:.0%}, "
            f"can't-decide up to {p.tie_peak:.0%}, {p.base_seconds:.1f} s per easy answer plus "
            f"up to {p.close_seconds:.1f} s on close calls. Source: {source}."
        ),
        "",
    ]
    if profile and profile.get("notes"):
        lines += ["Calibration notes:", ""] + [f"- {note}" for note in profile["notes"]] + [""]

    def method_label(m: str) -> str:
        return f"{m} (reference)" if m in REFERENCE else f"**{m}**" if m == "rankify" else m

    for j in judges:
        for n in sizes:
            title = {"human": " (the headline)", "perfect": " (sanity check)"}.get(j, "")
            lines += [
                f"## {n} items, {j} judge{title}",
                "",
                (
                    "Rounds and human minutes to reach each target (median over lists; `—` = "
                    "not reached in most lists within the budget; reached/lists in "
                    "brackets):"
                ),
                "",
                "| Method | Quick | Stable | Exact |",
                "|---|---|---|---|",
            ]
            for m in methods:
                cells = []
                for t in TARGETS:
                    rs = runs_for(n, j, m, t)
                    rounds = _median_or_none([r.reached(t) for r in rs])
                    mins = _median_or_none([r.minutes_to(t) for r in rs])
                    got = sum(r.reached(t) is not None for r in rs)
                    if rounds is None or mins is None:
                        cells.append(f"— ({got}/{len(rs)})")
                    else:
                        cells.append(f"{rounds:.0f} · {mins:.1f} min ({got}/{len(rs)})")
                lines.append(f"| {method_label(m)} | " + " | ".join(cells) + " |")
            if "rankify" in methods:
                lines += _rankify_stops(by, n, j) + _ratios(runs_for, methods, n, j)
            checkpoints = [c for c in (10, 25, 50, 100, 200, 400) if c <= budget_per_item * n]
            lines += [
                "",
                "Kendall τ with the hidden scores (median; 1 = identical):",
                "",
                "| Method | " + " | ".join(f"{c} rounds" for c in checkpoints) + " |",
                "|---|" + "---|" * len(checkpoints),
            ]
            for m in methods:
                rs = by[(n, j, m)]
                cells = []
                for c in checkpoints:
                    vals = [r.taus[min(c, len(r.taus)) - 1] for r in rs if r.taus]
                    cells.append(f"{statistics.median(vals):.2f}" if vals else "—")
                lines.append(f"| {method_label(m)} | " + " | ".join(cells) + " |")
            lines += [
                "",
                (
                    "Wasted questions, up to the round where Exact was reached (or the "
                    "whole budget): the answer already followed from earlier answers, or "
                    "the exact pair was asked before."
                ),
                "",
                "| Method | Already implied | Exact repeats | Stopped by itself |",
                "|---|---|---|---|",
            ]
            for m in methods:
                rs = by[(n, j, m)]
                cut = [r.reached("exact") or r.rounds for r in rs]
                asked = max(1, sum(cut))
                implied = sum(sum(r.implied[:c]) for r, c in zip(rs, cut, strict=True)) / asked
                repeats = sum(sum(r.repeats[:c]) for r, c in zip(rs, cut, strict=True)) / asked
                stopped = sum(r.finished for r in rs)
                lines.append(
                    f"| {method_label(m)} | {implied:.0%} | {repeats:.0%} | {stopped}/{len(rs)} |"
                )
            lines.append("")

    lines += [
        "## Confidence (methods that report it)",
        "",
        (
            "Measured on the final ranking of each list. Calibration error: how far stated "
            "Confidence is from the share of neighbour pairs actually in the right order "
            "(goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside "
            "the 90% range (goal G6: 85–95%)."
        ),
        "",
        "| Method | Items | Judge | Calibration error | Could be coverage |",
        "|---|---|---|---|---|",
    ]
    for m in methods:
        for n in sizes:
            for j in judges:
                rs = by[(n, j, m)]
                cal = [c for r in rs for c in r.calibration]
                cov = [c for r in rs for c in r.coverage]
                if cal:
                    lines.append(
                        f"| {method_label(m)} | {n} | {j} | {_ece(cal):.3f} | {np.mean(cov):.0%} |"
                    )
    lines.append("")

    lines += [
        "## Same answers, different order",
        "",
        "Each list's answers replayed in two shuffled orders through the method's scoring:",
        "",
    ]
    for m in ("rankify:exact", *ONLINE):
        rs = [r for r in results if r.method == m and r.reorder_changed_top is not None]
        label = m.partition(":")[0]
        if rs:
            changed = sum(r.reorder_changed_top for r in rs)
            tau = statistics.median(r.reorder_tau for r in rs)
            lines.append(
                f"- {label}: #1 changed in {changed}/{len(rs)} lists; median τ between the "
                f"two rankings {tau:.2f}"
            )
    lines.append("")

    lines += [
        "## Compute cost per round",
        "",
        "Median milliseconds per CLI call, in-process (real CLI code, no process start-up):",
        "",
        "| Method | next | answer | show |",
        "|---|---|---|---|",
    ]
    for m in methods:
        rs = [r for r in results if r.method.partition(":")[0] == m]
        cells = []
        for call in ("next", "answer", "show"):
            vals = [v for r in rs for v in r.ms.get(call, [])]
            cells.append(f"{statistics.median(vals):.1f}" if vals else "—")
        lines.append(f"| {method_label(m)} | " + " | ".join(cells) + " |")
    if real:
        lines += [
            "",
            (
                "A real `rankify` subprocess (20 items, includes Python start-up): "
                + ", ".join(f"{k} {v:.0f} ms" for k, v in real.items())
                + "."
            ),
        ]
    lines.append("")

    lines += [
        "## What each method offers",
        "",
        "| Feature | " + " | ".join(methods) + " |",
        "|---|" + "---|" * len(methods),
    ]
    for feature, per in FEATURES.items():
        default = _FEATURE_DEFAULT.get(feature, "no")
        cells = []
        for m in methods:
            if feature.startswith("Same answers") and m in (*ONLINE, "elo-close"):
                cells.append("no: updates one match at a time")
            else:
                cells.append(per.get(m, default))
        lines.append(f"| {feature} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Caveats",
        "",
        (
            "- Simulated judges, not people. The human judge's settings are guesses until a "
            "real session calibrates them."
        ),
        (
            "- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve "
            "rankify fits, so rankify gets no home advantage from it."
        ),
        (
            "- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; "
            "TrueSkill and openskill defaults). None was tuned."
        ),
        "- Human time counts answering only.",
        "",
    ]
    return "\n".join(lines)


def _rankify_stops(by, n: int, j: str) -> list[str]:
    """When rankify said it was done, in each mode: how often, how soon, and was it right?"""
    lines = [
        "",
        "When rankify stopped by itself, in each mode (median over lists that stopped):",
        "",
        "| Mode | Stopped by itself | Target really met at the stop | Rounds | Minutes |",
        "|---|---|---|---|---|",
    ]
    for t in TARGETS:
        rs = by[(n, j, f"rankify:{t}")]
        stopped = [r for r in rs if r.finished and r.rounds]
        met = sum(r.flags[t][-1] for r in stopped)
        rounds = statistics.median(r.rounds for r in stopped) if stopped else None
        mins = statistics.median(sum(r.seconds) / 60 for r in stopped) if stopped else None
        lines.append(
            f"| {t} | {len(stopped)}/{len(rs)} | {met}/{len(stopped)} | "
            + ("—" if rounds is None else f"{rounds:.0f}")
            + " | "
            + ("—" if mins is None else f"{mins:.1f}")
            + " |"
        )
    return lines


def _ratios(runs_for, methods, n: int, j: str) -> list[str]:
    """rankify's time to each target as a share of a baseline's (goals G1 and G2)."""
    lines = []
    for other, goal in (("elo", "G1: at most 50%"), ("just-sort-it", "G2: at most 80%")):
        if other not in methods:
            continue
        parts = []
        for t in ("quick", "stable", "exact"):
            mine = _median_or_none([r.minutes_to(t) for r in runs_for(n, j, "rankify", t)])
            theirs = _median_or_none([r.minutes_to(t) for r in runs_for(n, j, other, t)])
            if mine is None or theirs is None:
                parts.append(f"{t} n/a")
            else:
                parts.append(f"{t} {mine / theirs:.0%}")
        lines.append(f"- rankify's time as a share of {other}'s ({goal}): " + ", ".join(parts))
    return ["", *lines] if lines else []


def _ece(pairs: list[tuple[float, bool]]) -> float:
    conf = np.array([c for c, _ in pairs])
    right = np.array([r for _, r in pairs], dtype=float)
    total = 0.0
    for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
        m = (conf >= lo) & (conf < hi)
        if m.any():
            total += abs(conf[m].mean() - right[m].mean()) * m.sum()
    return total / len(conf)
