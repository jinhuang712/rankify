"""Estimate how a real judge answers, so the benchmark's simulated human can copy them.

Everything is in the benchmark's units: each answer perceives a score with normal noise of
spread 1 (Thurstone 1927), so two items a gap ``g`` apart are told apart with probability
``Phi(g / sqrt 2)``. Our fit uses the logistic curve, and the factor ``sqrt 2 / 1.702``
converts its scale to these units.

The direct estimates are biased. The gap between two items is itself estimated, and that
noise blurs every relationship measured against the gap (the errors-in-variables problem):
"close calls take longer" and "can't decide on near-ties" both come out too weak. So the
estimates are corrected with a parametric bootstrap: simulate sessions like the judge's
own from the first estimates, run the same estimator on them, and subtract the bias it
shows (Efron & Tibshirani 1993, ch. 10).

Picks and orderings are timed against the same model the benchmark's judge uses for them
(one call per neighbour in the judge's order for an ordering; the call between the best
two plus half an easy call per other item for a pick), with the judge's own pair pace.
The median of real time over modelled time is the judge's ``set_time_scale``. In
simulation it reads about 10% low, because the fitted gaps are noisy.

One session still gives rough numbers. The profile keeps the evidence (answer count,
repeats) and notes next to the estimates, so nobody reads more precision into them.
"""

import itertools
import math
from collections import Counter
from dataclasses import asdict, dataclass, field, replace

import numpy as np

from rankify.engine.fit import fit_pairs
from rankify.engine.judge import HumanParams, human_answer
from rankify.engine.model import A_WINS, B_WINS, TIE, Pairs, Prior

_SQRT2 = math.sqrt(2.0)
LOGISTIC_TO_NORMAL = _SQRT2 / 1.702  # our fitted scores -> benchmark units
CALIBRATION_PRIOR = Prior(sigma=5.0)  # weak, so the spread of scores is barely shrunk
FATIGUE_CAP = 1.6
MAX_SECONDS = 60.0  # longer answers mean the judge stepped away; they are left out
REPEAT_SHARE = 0.15  # matches the calibration planner in the service
_REPEAT_GAP = 8


def _phi(x):
    """Normal CDF, vectorised (tanh approximation, error under 0.001)."""
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + np.tanh(0.7978845608 * (x + 0.044715 * x**3)))


# ---------------------------------------------------------------- the benchmark's list shape


def benchmark_scores(n: int, spread: float, rng: np.random.Generator) -> np.ndarray:
    """Hidden scores for a benchmark list: a few clear favourites and a crowded middle."""
    return spread * rng.standard_t(3, n)


def neighbour_accuracy(scores: np.ndarray) -> float:
    """Median chance that the judge orders two neighbouring items correctly."""
    s = np.sort(np.asarray(scores))[::-1]
    return float(np.median(_phi((s[:-1] - s[1:]) / _SQRT2)))


def generator_accuracy(n: int, spread: float, lists: int = 300) -> float:
    """``neighbour_accuracy`` of benchmark lists of ``n`` items, over many lists."""
    return float(
        np.median(
            [
                neighbour_accuracy(benchmark_scores(n, spread, np.random.default_rng(10**6 + k)))
                for k in range(lists)
            ]
        )
    )


def spread_matching(n: int, accuracy: float) -> float:
    """The benchmark spread whose lists are as hard as a list with this neighbour accuracy."""
    lo, hi = 0.02, 30.0
    for _ in range(30):  # accuracy grows with the spread, so bisect on a log scale
        mid = math.sqrt(lo * hi)
        if generator_accuracy(n, mid) < accuracy:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


# ---------------------------------------------------------------- the profile


@dataclass
class JudgeProfile:
    # Settings for the benchmark's human judge (the fields of HumanParams).
    noise: float
    fatigue: float
    fatigue_cap: float
    first_bonus: float
    lapse: float
    tie_peak: float
    tie_width: float
    base_seconds: float
    close_seconds: float
    close_width: float
    tie_seconds: float
    score_spread: float
    # The evidence behind them.
    answers: int
    items: int
    neighbour_accuracy: float
    repeats: int
    repeat_disagreement: float | None
    repeat_disagreement_expected: float | None
    bootstrap_sessions: int
    set_time_scale: float = 1.0  # picks and orderings, against the guessed time model
    set_answers: int = 0  # timed picks and orderings behind it
    set_seconds: dict = field(default_factory=dict)  # median seconds, by kind and size
    measured: list[str] = field(default_factory=list)  # settings this session could measure
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def judge_params(self) -> HumanParams:
        """The measured settings; everything else keeps the default guess."""
        keys = set(self.measured) & set(HumanParams.__dataclass_fields__)
        return replace(HumanParams(), **{k: getattr(self, k) for k in keys})


# How many answers a setting needs before a session measures it well enough to use. From a
# recovery check: simulated judges with known settings, estimated back (EXPERIMENT.md).
MIN_ANSWERS = {
    "base_seconds": 60,
    "score_spread": 60,
    "tie_peak": 60,
    "tie_seconds": 60,
    "tie_width": 300,
    "close_seconds": 300,
    "close_width": 300,
    "fatigue": 300,
}
NOT_YET_MEASURABLE = ("first_bonus", "lapse")  # too noisy even at 400 answers
MIN_SET_ANSWERS = 8  # timed picks and orderings before set_time_scale counts as measured
# Settings whose direct estimate is biased by noisy gaps, so the bootstrap corrects them.
_CORRECTED = ("tie_peak", "tie_width", "close_seconds", "close_width", "accuracy")


# Estimated quantities, each with its valid range.
_RANGES = {
    "first_bonus": (-2.0, 2.0),
    "lapse": (0.0, 0.3),
    "fatigue": (0.0, 0.02),
    "tie_peak": (0.0, 0.95),
    "tie_width": (0.05, 3.0),
    "base_seconds": (0.3, 30.0),
    "close_seconds": (0.0, 30.0),
    "close_width": (0.05, 3.0),
    "tie_seconds": (0.0, 30.0),
    "accuracy": (0.5, 0.999),
}


def estimate_profile(
    n: int,
    a,
    b,
    y,
    seconds,
    *,
    set_rounds=(),
    planned: bool = False,
    bootstrap: int = 30,
    seed: int = 0,
) -> JudgeProfile:
    """Estimate a judge profile from one judge's pair rounds, in log order.

    ``a``/``b`` are the positions of the items shown first/second, ``y`` is A_WINS, B_WINS or
    TIE, and ``seconds`` is each answer's time (or None when unknown). ``set_rounds`` holds
    (kind, the shown items' fitted scores in the judge's order with the chosen item first,
    seconds) for timed picks and orderings. ``planned`` says some pairs were chosen by the
    planner rather than at random. ``bootstrap`` simulated sessions correct the bias of the
    direct estimates; 0 turns the correction off.
    """
    a, b, y = (np.asarray(v, dtype=np.int64) for v in (a, b, y))
    m = len(y)
    raw = _estimate_raw(n, a, b, y, seconds)
    items = raw["items"]
    est = {k: raw[k] for k in _RANGES}
    if bootstrap:
        truth = _params_from(est)
        spread = spread_matching(items, est["accuracy"])
        rng = np.random.default_rng([seed, m, items])
        sims = [
            _estimate_raw(items, *simulate_session(items, m, truth, spread, rng))
            for _ in range(bootstrap)
        ]
        for k in _CORRECTED:
            lo, hi = _RANGES[k]
            bias = float(np.mean([s[k] for s in sims])) - est[k]
            est[k] = float(np.clip(est[k] - bias, lo, hi))

    measured = [k for k, need in MIN_ANSWERS.items() if m >= need]
    if raw["ties"] < 3:
        measured = [k for k in measured if not k.startswith("tie_")]
    if raw["timed"] < 20:
        measured = [k for k in measured if not k.endswith("_seconds") and k != "close_width"]
    notes = []
    waiting = [k for k, need in MIN_ANSWERS.items() if k not in measured and m < need]
    if waiting:
        notes.append(
            f"With {m} answers, these keep the default guess: {', '.join(waiting)}. "
            f"About {max(MIN_ANSWERS[k] for k in waiting)} answers measure them; more sittings "
            "on the same list add up."
        )
    notes.append(
        f"{' and '.join(NOT_YET_MEASURABLE)} keep the default guess at any length: one judge's "
        "session is too noisy to measure them."
    )
    if raw["ties"] < 3:
        notes.append('Fewer than 3 "can\'t decide" answers, so the tie settings keep the guess.')
    if raw["repeats"] < 10:
        notes.append(f"Only {raw['repeats']} repeated pairs: the consistency check is weak.")
    if planned:
        notes.append(
            "Some pairs were chosen by the planner, which leans toward close calls; the bias "
            "corrections assume random pairs, so take the close-call and can't-decide settings "
            "as rough."
        )
    # Timed against the pace the benchmark's judge will use: measured settings where this
    # session measured them, the guesses elsewhere, so the scale fits the judge it scales.
    pace = {
        k: est[k] if k in measured else getattr(HumanParams(), k)
        for k in ("base_seconds", "close_seconds", "close_width")
    }
    scale, set_answers, set_seconds = estimate_set_time_scale(
        set_rounds, pace["base_seconds"], pace["close_seconds"], pace["close_width"]
    )
    if set_answers >= MIN_SET_ANSWERS:
        measured.append("set_time_scale")
        if raw["timed"] < 20:
            notes.append(
                "Picks and orderings are timed against the guessed pair pace, because few pairs "
                "were timed."
            )
    elif set_rounds:
        notes.append(
            f"Only {set_answers} timed picks and orderings: set_time_scale keeps the guess "
            f"(needs {MIN_SET_ANSWERS})."
        )
    if raw["timed"] < 20:
        notes.append("Few timed answers: the time settings keep the guess.")
    elif est["base_seconds"] + est["close_seconds"] > 15:
        notes.append("Answers took over 15 s on average: the times probably include typing.")

    return JudgeProfile(
        noise=1.0,
        fatigue=est["fatigue"],
        fatigue_cap=FATIGUE_CAP,
        first_bonus=est["first_bonus"],
        lapse=est["lapse"],
        tie_peak=est["tie_peak"],
        tie_width=est["tie_width"],
        base_seconds=est["base_seconds"],
        close_seconds=est["close_seconds"],
        close_width=est["close_width"],
        tie_seconds=est["tie_seconds"],
        score_spread=spread_matching(items, est["accuracy"]),
        answers=m,
        items=items,
        neighbour_accuracy=est["accuracy"],
        repeats=raw["repeats"],
        repeat_disagreement=raw["repeat_observed"],
        repeat_disagreement_expected=raw["repeat_expected"],
        bootstrap_sessions=bootstrap,
        set_time_scale=scale,
        set_answers=set_answers,
        set_seconds=set_seconds,
        measured=measured,
        notes=notes,
    )


def estimate_set_time_scale(set_rounds, base: float, close: float, width: float):
    """(set_time_scale, timed set rounds used, median seconds by "kind size") from timed
    picks and orderings. Scores are the list's fitted scores, converted to benchmark units."""

    def call(gap: float) -> float:
        return base + close * math.exp(-abs(gap) / width)

    ratios, by_size = [], {}
    for kind, scores, sec in set_rounds:
        if not 0.2 < sec < 3 * MAX_SECONDS:
            continue
        s = [v * LOGISTIC_TO_NORMAL for v in scores]
        if kind == "rank":
            modelled = sum(call(x - y) for x, y in itertools.pairwise(s))
        else:
            modelled = call(s[0] - max(s[1:])) + 0.5 * base * (len(s) - 2)
        ratios.append(sec / modelled)
        by_size.setdefault(f"{kind} {len(s)}", []).append(sec)
    if not ratios:
        return 1.0, 0, {}
    medians = {k: float(np.median(v)) for k, v in sorted(by_size.items())}
    return float(np.median(ratios)), len(ratios), medians


def simulate_session(n: int, m: int, params: HumanParams, spread: float, rng):
    """A calibration session like the real one: random pairs, some repeated with sides swapped."""
    theta = benchmark_scores(n, spread, rng)
    a, b, y, secs = [], [], [], []
    asked: Counter = Counter()
    history: list[tuple[int, int]] = []
    for t in range(m):
        pair = None
        if rng.random() < REPEAT_SHARE and len(history) > _REPEAT_GAP:
            pool = [p for p in history[:-_REPEAT_GAP] if asked[frozenset(p)] == 1]
            if pool:
                first, second = pool[int(rng.integers(len(pool)))]
                pair = (second, first)
        if pair is None:
            i, j = rng.choice(n, 2, replace=False)
            pair = (int(i), int(j))
        pick, sec = human_answer(params, rng, float(theta[pair[0]] - theta[pair[1]]), t)
        a.append(pair[0])
        b.append(pair[1])
        y.append(TIE if pick is None else A_WINS if pick == 1 else B_WINS)
        secs.append(sec)
        asked[frozenset(pair)] += 1
        history.append(pair)
    return np.array(a), np.array(b), np.array(y), secs


def _params_from(est: dict) -> HumanParams:
    keys = set(HumanParams.__dataclass_fields__) & set(est)
    return replace(HumanParams(fatigue_cap=FATIGUE_CAP), **{k: est[k] for k in keys})


# ---------------------------------------------------------------- the direct estimates


def _estimate_raw(n: int, a, b, y, seconds) -> dict:
    a, b, y = (np.asarray(v, dtype=np.int64) for v in (a, b, y))
    m = len(y)
    fit = fit_pairs(n, Pairs.of(a, b, y), CALIBRATION_PRIOR)
    theta = fit.theta * LOGISTIC_TO_NORMAL
    bonus = fit.bias * LOGISTIC_TO_NORMAL
    decided = y != TIE
    scale, lapse, fatigue = _fit_scale_lapse_fatigue(
        (theta[a] - theta[b])[decided] + bonus, (y == A_WINS)[decided], np.arange(m)[decided]
    )
    theta = theta * scale
    gap = np.abs(theta[a] - theta[b])
    seen = np.unique(np.concatenate([a, b]))
    tie_peak, tie_width = _fit_ties(gap, ~decided)
    base, close, width, tie_extra, timed = _fit_times(gap, seconds, ~decided)
    repeats, observed, expected = _repeat_check(a, b, y, theta)
    return {
        "first_bonus": float(bonus * scale),
        "lapse": lapse,
        "fatigue": fatigue,
        "tie_peak": tie_peak,
        "tie_width": tie_width,
        "base_seconds": base,
        "close_seconds": close,
        "close_width": width,
        "tie_seconds": tie_extra,
        "accuracy": neighbour_accuracy(theta[seen]),
        "items": len(seen),
        "ties": int((~decided).sum()),
        "timed": timed,
        "repeats": repeats,
        "repeat_observed": observed,
        "repeat_expected": expected,
    }


def _fit_scale_lapse_fatigue(d, first_won, t) -> tuple[float, float, float]:
    """Maximum likelihood over a grid. The scale lets noise rise over the session without the
    fitted scores simply absorbing it."""
    best, best_ll = (1.0, 0.0, 0.0), -math.inf
    lapses = np.linspace(0.0, 0.2, 41)[:, None]
    for scale in np.linspace(0.6, 2.0, 15):
        for fatigue in np.linspace(0.0, 0.02, 21):
            sd = np.minimum(1.0 + fatigue * t, FATIGUE_CAP)
            p = _phi(scale * d / (_SQRT2 * sd))
            q = lapses / 2 + (1 - lapses) * p[None, :]
            q = np.clip(np.where(first_won[None, :], q, 1 - q), 1e-12, 1.0)
            ll = np.log(q).sum(axis=1)
            k = int(np.argmax(ll))
            if ll[k] > best_ll:
                best, best_ll = (float(scale), float(lapses[k, 0]), float(fatigue)), float(ll[k])
    return best


def _fit_ties(gap, tied) -> tuple[float, float]:
    """P(can't decide) = peak * exp(-gap / width), by maximum likelihood over a grid."""
    if not tied.any():
        return 0.0, 0.3
    peaks = np.linspace(0.01, 0.95, 95)[:, None]
    best, best_ll = (0.0, 0.3), -math.inf
    for width in np.geomspace(0.05, 3.0, 40):
        p = np.clip(peaks * np.exp(-gap / width)[None, :], 1e-12, 1 - 1e-12)
        ll = np.where(tied[None, :], np.log(p), np.log1p(-p)).sum(axis=1)
        k = int(np.argmax(ll))
        if ll[k] > best_ll:
            best, best_ll = (float(peaks[k, 0]), float(width)), float(ll[k])
    return best


def _fit_times(gap, seconds, tied) -> tuple[float, float, float, float, int]:
    """seconds = base + close * exp(-gap / width), by least squares over a grid of widths."""
    s = np.array([np.nan if v is None else v for v in seconds], dtype=float)
    ok = np.isfinite(s) & (s > 0.2) & (s < MAX_SECONDS)
    use = ok & ~tied
    timed = int(use.sum())
    defaults = HumanParams()
    if timed < 20:
        return (
            defaults.base_seconds,
            defaults.close_seconds,
            defaults.close_width,
            defaults.tie_seconds,
            timed,
        )
    g, sec = gap[use], s[use]
    best, best_sse = (float(np.median(sec)), 0.0, 0.6), math.inf
    for width in np.geomspace(0.05, 3.0, 40):
        x = np.exp(-g / width)
        design = np.stack([np.ones_like(x), x], 1)
        (base, close), *_ = np.linalg.lstsq(design, sec, rcond=None)
        if close < 0 or base <= 0:
            continue
        sse = float(np.sum((sec - base - close * x) ** 2))
        if sse < best_sse:
            best, best_sse = (float(base), float(close), float(width)), sse
    base, close, width = best
    tie_extra = defaults.tie_seconds
    timed_ties = ok & tied
    if timed_ties.any():
        predicted = base + close * np.exp(-gap[timed_ties] / width)
        tie_extra = max(0.0, float(np.median(s[timed_ties] - predicted)))
    return base, close, width, tie_extra, timed


def _repeat_check(a, b, y, theta) -> tuple[int, float | None, float | None]:
    """How often a repeated pair got a different winner, against what the fit expects."""
    winners: dict[frozenset, list[int]] = {}
    for first, second, outcome in zip(a.tolist(), b.tolist(), y.tolist(), strict=True):
        if outcome == TIE:
            continue
        winner = first if outcome == A_WINS else second
        winners.setdefault(frozenset((first, second)), []).append(winner)
    pairs = [(k, v) for k, v in winners.items() if len(v) >= 2]
    if not pairs:
        return 0, None, None
    observed = float(np.mean([len(set(v[:2])) == 2 for _, v in pairs]))
    expected = []
    for key, _ in pairs:
        i, j = tuple(key)
        q = float(_phi((theta[i] - theta[j]) / _SQRT2))
        expected.append(2 * q * (1 - q))
    return len(pairs), observed, float(np.mean(expected))
