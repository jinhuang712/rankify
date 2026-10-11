"""Rounds left: play the rest of the session forward in simulation.

Each simulation draws plausible "true" scores from the current fit and lets a simulated
judge answer the way the model expects (Bradley–Terry). A cheap planner asks pairs and
stops by the same rules as the real one: first looks, the mode's target, and the
"nothing worth asking" floor. The spread of the round counts over many simulations gives
the range, like "about 14 (10–19)".

Refitting after every simulated answer would take far too long, so each answer updates the
fit's Gaussian in closed form instead: one moment-matching step for a probit answer, the
update TrueSkill makes for a game (Herbrich, Minka & Graepel 2007). The logistic curve is
matched by a probit curve with scale 1.702. Could be, and how much each pair matters for
the mode, come from fewer posterior draws than the screen uses.

The forecast plans pairs only. On a list that also asks picks and orderings, the real
session can take fewer rounds than forecast.
"""

import math
from collections.abc import Generator
from dataclasses import dataclass
from statistics import NormalDist
from time import perf_counter

import numpy as np

from rankify.engine import stop
from rankify.engine.planner import (
    FLOOR_ANSWERS,
    FLOOR_BITS,
    MIN_LOOKS,
    STABLE_TIER_WEIGHT,
    order_information,
    order_information_over,
)

FORECAST_NAME = "adf-pairs-0.2"
LOW_Q, HIGH_Q = 0.1, 0.9  # the range shown: 10th to 90th percentile
_PROBIT = 1.702  # sigmoid(d) ~ Phi(d / 1.702)
_WINDOW = 3  # candidate pairs: each item against the next few in the current order
_DRAWS = 96  # posterior draws for Could be and relevance
_ALL_PAIRS = 30  # above this many items, only pair each item with the next few
_REFRESH = 4  # simulated rounds between fresh posterior draws
_PAUSE_EVERY = 4  # simulated rounds between pauses of forecast_steps
_NODES16 = np.array([NormalDist().inv_cdf((k + 0.5) / 16) for k in range(16)])


@dataclass(frozen=True)
class Forecast:
    """Rounds left. ``None`` means "unknown, but more": then ``at_least`` gives a floor."""

    median: int | None
    low: int | None  # 10th percentile
    high: int | None  # 90th percentile
    at_least: int | None
    sims: int  # simulations run
    capped: int  # simulations cut short (too many rounds, or out of time)
    ms: float


class _Draws:
    """Ranks in posterior draws, recomputed after every simulated answer. They give Could be
    and how much each pair matters, the same way the real planner gets them. (A normal
    approximation of each rank was tried first; it treats "j is above i" as independent
    for every j, which makes ranks far too certain early on.)"""

    def __init__(self, m: np.ndarray, s: np.ndarray, rng: np.random.Generator):
        k = len(m)
        try:
            chol = np.linalg.cholesky(s + 1e-12 * np.eye(k))
        except np.linalg.LinAlgError:
            w, v = np.linalg.eigh(s)
            chol = v * np.sqrt(np.clip(w, 0.0, None))
        sample = m + rng.standard_normal((_DRAWS, k)) @ chol.T
        self.ranks = np.empty((_DRAWS, k), dtype=np.int64)
        self.ranks[np.arange(_DRAWS)[:, None], np.argsort(-sample, axis=1)] = np.arange(1, k + 1)

    def ranges(self, order: np.ndarray) -> list[tuple[int, int, int]]:
        """(position, rank_lo, rank_hi) best first: a 90% range, as `summarize` makes it."""
        lo = np.quantile(self.ranks, 0.05, axis=0, method="lower")
        hi = np.quantile(self.ranks, 0.95, axis=0, method="higher")
        return [
            (int(p), min(int(lo[p]), place), max(int(hi[p]), place))
            for place, p in enumerate(order, start=1)
        ]

    def relevance(self, mode: str, i: np.ndarray, j: np.ndarray) -> np.ndarray:
        """The chance either item belongs to the part the mode settles (planner._Region)."""
        if mode == "exact":
            return np.ones(len(i))
        k = self.ranks.shape[1]
        top = self.ranks <= (3 if mode == "quick" else stop.top_size(k) + 1)
        rel = np.mean(top[:, i] | top[:, j], axis=0)
        return np.maximum(rel, STABLE_TIER_WEIGHT) if mode == "stable" else rel


def _update(m: np.ndarray, s: np.ndarray, i: int, j: int, i_won: bool) -> None:
    """One probit moment-matching step for "i beat j" (or the reverse), in place."""
    y = 1.0 if i_won else -1.0
    col = s[:, i] - s[:, j]
    var = col[i] - col[j]
    denom2 = _PROBIT**2 + max(var, 0.0)
    denom = math.sqrt(denom2)
    t = y * (m[i] - m[j]) / denom
    cdf = 0.5 * math.erfc(-t / math.sqrt(2.0))
    pdf = math.exp(-0.5 * t * t) / math.sqrt(2.0 * math.pi)
    v = pdf / cdf if cdf > 1e-300 else -t  # Mills ratio; -t far in the tail
    w = v * (v + t)
    m += y * col * (v / denom)
    s -= np.outer(col, col) * (w / denom2)


def _pairs(order: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Candidate pairs: all of them on short lists, else each item against the next few."""
    k = len(order)
    if k <= _ALL_PAIRS:
        a, b = np.triu_indices(k, 1)
    else:
        a = np.array([x for x in range(k) for d in range(1, _WINDOW + 1) if x + d < k])
        b = np.array([x + d for x in range(k) for d in range(1, _WINDOW + 1) if x + d < k])
    return order[a], order[b]


class _Belief:
    """One simulation's Gaussian belief, with posterior draws refreshed every few answers."""

    def __init__(self, m: np.ndarray, s: np.ndarray, rng: np.random.Generator):
        self.m, self.s, self.rng = m, s, rng
        self._draws: _Draws | None = None
        self._age = 0

    def draws(self, fresh: bool) -> _Draws:
        if fresh or self._draws is None or self._age >= _REFRESH:
            self._draws, self._age = _Draws(self.m, self.s, self.rng), 0
        return self._draws

    def update(self, i: int, j: int, i_won: bool) -> None:
        _update(self.m, self.s, i, j, i_won)
        self._age += 1


def _plan(mode, order, m, s, nb, looks, draws_for) -> tuple[int, int] | None:
    """The pair the cheap planner asks, or None when it would stop. ``draws_for(fresh)``
    gives posterior draws, recent or (``fresh=True``) of the current state."""
    unseen = [p for p in order if looks[p] < MIN_LOOKS]
    draws = draws_for(False)
    # Stop only on fresh draws: the neighbours alone first, then Could be.
    if not unseen and stop.target_reached(mode, nb):
        draws = draws_for(True)
        if stop.target_reached(mode, nb, draws.ranges(order)):
            return None
    if unseen:
        new = min(unseen, key=lambda p: looks[p])
        others = np.array([p for p in order if p != new])
        i, j = np.full(len(others), new), others
    else:
        play = np.zeros(len(order), dtype=bool)
        play[list(stop.in_play(mode, draws.ranges(order), nb))] = True
        i, j = _pairs(order)
        keep = play[i] | play[j]
        if not keep.any():
            return None
        i, j = i[keep], j[keep]
    mu = m[i] - m[j]
    var = np.maximum(s[i, i] + s[j, j] - 2 * s[i, j], 1e-12)
    relevance = np.ones(len(i)) if unseen else draws.relevance(mode, i, j)
    gain = order_information(mu, var, _NODES16) * relevance
    best = np.argsort(-gain, kind="stable")[:5]
    # Eight answers teach at least as much as one, so the floor can only stop the session
    # when even the best single answer teaches less than it.
    if not unseen and gain[best[0]] < FLOOR_BITS:
        later = order_information_over(mu[best], var[best], FLOOR_ANSWERS)  # as the planner
        if (later * relevance[best]).max(initial=0.0) < FLOOR_BITS:
            return None
    return int(i[best[0]]), int(j[best[0]])


def forecast_rounds(*args, **kwargs) -> Forecast:
    """Rounds left until rankify stops in ``mode``; see ``forecast_steps``."""
    steps = forecast_steps(*args, **kwargs)
    while True:
        try:
            next(steps)
        except StopIteration as finished:
            return finished.value


def forecast_steps(
    mode: str,
    theta: np.ndarray,
    cov: np.ndarray,
    active: list[int],
    looks: dict[int, int],
    seed: int,
    *,
    budget_ms: float = 800.0,
    min_sims: int = 8,
    max_sims: int = 64,
    cap: int | None = None,
) -> Generator[None, None, Forecast]:
    """Rounds left until rankify stops in ``mode``, as a generator that pauses every few
    simulated rounds and returns the ``Forecast``. A terminal UI runs it between keypresses,
    so the next round never waits for it. ``active`` holds the positions of the ranked
    items, and ``looks`` how many answers each position has been in.

    Simulations run until ``max_sims``, or until ``budget_ms`` is spent and at least
    ``min_sims`` are done. Past twice the budget, the running simulation is cut short. A
    simulation that is cut short, or still asking after ``cap`` rounds, only says "at
    least this many"; when that leaves the median unknown, the forecast is "more than"."""
    t0 = perf_counter()
    pos = np.asarray(active, dtype=np.int64)
    k = len(pos)
    cap = cap or 20 * max(k, 2)
    if k < 2:
        return Forecast(0, 0, 0, None, 0, 0, 0.0)
    m0 = np.asarray(theta, dtype=float)[pos]
    s0 = np.asarray(cov, dtype=float)[np.ix_(pos, pos)]
    looks0 = np.array([looks.get(int(p), 0) for p in pos])
    try:
        chol = np.linalg.cholesky(s0 + 1e-12 * np.eye(k))
    except np.linalg.LinAlgError:
        w, v = np.linalg.eigh(s0)
        chol = v * np.sqrt(np.clip(w, 0.0, None))
    rng = np.random.default_rng([seed, 23])

    def elapsed() -> float:
        return (perf_counter() - t0) * 1000

    done: list[float] = []  # rounds, or infinity where a simulation was cut short
    lower: list[int] = []  # rounds reached by simulations cut short: at least that many left
    while len(done) < max_sims and not (len(done) >= min_sims and elapsed() > budget_ms):
        truth = m0 + chol @ rng.standard_normal(k)
        belief, seen = _Belief(m0.copy(), s0.copy(), rng), looks0.copy()
        m, s = belief.m, belief.s
        rounds, cut = 0, False
        while True:
            if rounds >= cap or (rounds % 16 == 0 and elapsed() > 2 * budget_ms):
                cut = True
                break
            order = np.argsort(-np.round(m, 9), kind="stable")
            # The real stop rules use the exact normal curve; an approximation here moved
            # the thresholds enough to stop simulations a round early, or run them long.
            pair = _plan(mode, order, m, s, stop.neighbours(m, s, order), seen, belief.draws)
            if pair is None:
                break
            i, j = pair
            i_won = rng.random() < 1.0 / (1.0 + math.exp(-(truth[i] - truth[j])))
            belief.update(i, j, i_won)
            seen[i] += 1
            seen[j] += 1
            rounds += 1
            if rounds % _PAUSE_EVERY == 0:
                yield
        done.append(math.inf if cut else float(rounds))
        if cut:
            lower.append(rounds)
        yield  # also between simulations: near the end, most stop within a few rounds
        if elapsed() > 2 * budget_ms:
            break
    c = np.sort(np.array(done))

    def quantile(q: float, method: str) -> int | None:
        v = float(np.quantile(c, q, method=method))
        return None if math.isinf(v) else int(v)

    median = quantile(0.5, "higher")
    return Forecast(
        median=median,
        low=quantile(LOW_Q, "lower"),
        high=quantile(HIGH_Q, "higher"),
        at_least=min(lower) if lower and median is None else None,
        sims=len(c),
        capped=len(lower),
        ms=elapsed(),
    )
