"""Rounds left: play the rest of the session forward in simulation.

Each simulation draws plausible "true" scores from the current fit and lets a simulated
judge answer. A cheap planner asks what the real one would, and stops by the same rules:
first looks, the mode's target, and the "nothing worth asking" floor. On a list with pick
and rank rounds, it grows sets the way the real planner does and weighs them against pairs
by information per second, with the judge's own times. The spread of the round counts over
many simulations gives the range, like "about 14 (10–19)".

The simulated judge answers as the model expects (Bradley–Terry pairs, Plackett–Luce sets)
with two habits on top, in ``Habits``: "can't decide" at the rate the fit has learned for
this list (Davidson's tie weight), and answers that get noisier as the session wears on.
Fatigue can't be measured from one short list, so it is a guess until a real session
measures it. Occasional answers at random (lapses) are left out: the fit already narrows
its scores to explain the upsets it has seen, so simulating lapses on top counted them
twice, and forecasts ran long.

The fit learns how widely scores spread (the prior width) from the answers, and early on
that width is unsure: on the benchmark's lists it dips from 1.5 to about 1.0 after ten
answers and climbs back to 1.3–1.75 later. So each simulation draws a width from what is
known about it, and redoes the fit's Gaussian for that width with the same answers, before
drawing true scores from it and starting the simulated fit there.

Refitting after every simulated answer would take far too long, so each answer updates the
fit's Gaussian in closed form instead. A pair answer takes one moment-matching step for a
probit answer, the update TrueSkill makes for a game (Herbrich, Minka & Graepel 2007), with
the logistic curve matched by a probit curve with scale 1.702. A pick, a ranking or "can't
decide" finds the posterior mode of the shown items with a few damped Newton steps and
takes the covariance from the answer's information there (a Laplace update; MacKay 1992),
as the real fit does over all answers; the other items follow through their covariance. Could be, and how much each pair matters for the mode,
come from fewer posterior draws than the screen uses.
"""

import math
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from statistics import NormalDist
from time import perf_counter

import numpy as np

from rankify.engine import stop
from rankify.engine.fit import DEFAULT_SIGMA_PRIOR
from rankify.engine.judge import HumanParams
from rankify.engine.model import Prior
from rankify.engine.planner import (
    FLOOR_ANSWERS,
    FLOOR_BITS,
    MIN_LOOKS,
    PAIRS_ONLY,
    STABLE_TIER_WEIGHT,
    Candidate,
    Timing,
    _grow_sets,
    _pool,
    closeness,
    order_information,
    order_information_over,
    set_gain,
)

FORECAST_NAME = "adf-mixed-0.3"
LOW_Q, HIGH_Q = 0.1, 0.9  # the range shown: 10th to 90th percentile
_PROBIT = 1.702  # sigmoid(d) ~ Phi(d / 1.702)
_WINDOW = 3  # candidate pairs: each item against the next few in the current order
_DRAWS = 96  # posterior draws for Could be and relevance
_ALL_PAIRS = 30  # above this many items, only pair each item with the next few
_REFRESH = 4  # simulated rounds between fresh posterior draws
_PAUSE_EVERY = 4  # simulated pair rounds between pauses of forecast_steps
_SET_SEEDS = 1  # the real planner grows sets from two pairs; two changed little here
_NODES16 = np.array([NormalDist().inv_cdf((k + 0.5) / 16) for k in range(16)])


@dataclass(frozen=True)
class Habits:
    """How the simulated judge answers, beyond the model. ``tie`` comes from the list's fit;
    fatigue is the benchmark's guessed human judge until a real session measures it."""

    fatigue: float = HumanParams.fatigue  # noise grows by this share per call made...
    fatigue_cap: float = HumanParams.fatigue_cap  # ...up to this multiple
    tie: float = math.exp(Prior.tie_mean)  # Davidson's nu: "can't decide" between equals

    def noise(self, effort: int) -> float:
        """The judge's noise after ``effort`` calls, as a multiple of a fresh judge's."""
        return min(1.0 + self.fatigue * effort, self.fatigue_cap)

    def past_noise(self, efforts: Sequence[int]) -> float:
        """The average noise over past calls, each made ``effort`` calls into its sitting:
        the noise the fit's scores already reflect."""
        if len(efforts) == 0:
            return 1.0
        e = np.asarray(efforts, dtype=float)
        return float(np.mean(np.minimum(1.0 + self.fatigue * e, self.fatigue_cap)))


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
    """Ranks in posterior draws, recomputed after every few simulated answers. They give
    Could be and how much each pair matters, the same way the real planner gets them. (A
    normal approximation of each rank was tried first; it treats "j is above i" as
    independent for every j, which makes ranks far too certain early on.)"""

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
        self._top: dict[str, np.ndarray] = {}

    def ranges(self, order: np.ndarray) -> list[tuple[int, int, int]]:
        """(position, rank_lo, rank_hi) best first: a 90% range, as `summarize` makes it."""
        lo = np.quantile(self.ranks, 0.05, axis=0, method="lower")
        hi = np.quantile(self.ranks, 0.95, axis=0, method="higher")
        return [
            (int(p), min(int(lo[p]), place), max(int(hi[p]), place))
            for place, p in enumerate(order, start=1)
        ]

    def top(self, mode: str) -> np.ndarray:
        """(draws, items): whether each item is in the part the mode settles (planner._Region)."""
        if mode not in self._top:
            k = self.ranks.shape[1]
            self._top[mode] = self.ranks <= (3 if mode == "quick" else stop.top_size(k) + 1)
        return self._top[mode]

    def relevance(self, mode: str, i: np.ndarray, j: np.ndarray) -> np.ndarray:
        """The chance either item belongs to the part the mode settles."""
        if mode == "exact":
            return np.ones(len(i))
        top = self.top(mode)
        rel = np.mean(top[:, i] | top[:, j], axis=0)
        return np.maximum(rel, STABLE_TIER_WEIGHT) if mode == "stable" else rel


class _Region:
    """``planner._Region.within`` from the simulation's draws, for growing sets."""

    def __init__(self, mode: str, draws: _Draws, everything: bool):
        self.mode = mode
        self.top = None if everything or mode == "exact" else draws.top(mode)

    def within(self, sets: np.ndarray) -> np.ndarray:
        c, k = sets.shape
        if self.top is None:
            return np.ones((c, k, k))
        t = self.top[:, sets]
        rel = np.mean(t[..., :, None] | t[..., None, :], axis=0)
        return np.maximum(rel, STABLE_TIER_WEIGHT) if self.mode == "stable" else rel


# ---------------------------------------------------------------- belief updates


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


# An answer's log-likelihood at the shown items' scores u: (value, gradient, information).
LogLik = Callable[[np.ndarray], tuple[float, np.ndarray, np.ndarray]]


def _laplace(m: np.ndarray, s: np.ndarray, idx: np.ndarray, loglik: LogLik) -> None:
    """Update the belief for an answer about the items ``idx``, in place: find the posterior
    mode of the shown items by damped Newton steps (a few suffice for 2 to 5 items), take
    the covariance from the answer's information there, as the real fit does (a Laplace
    update), and carry the change to the other items through their covariance. A single
    step from the current mean overshoots when an answer is surprising and the scores are
    still unsure: a "can't decide" could flip the pair's order."""
    k = len(idx)
    prior_m = m[idx].copy()
    block = s[np.ix_(idx, idx)]
    prec = np.linalg.inv(block)

    def objective(u: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        value, g, f = loglik(u)
        d = u - prior_m
        return value - 0.5 * d @ prec @ d, g - prec @ d, f

    u = prior_m.copy()
    value, grad, f = objective(u)
    for _ in range(20):
        step = np.linalg.solve(f + prec, grad)
        t = 1.0
        while True:  # the objective is concave; halve a step that goes past the peak
            new = objective(u + t * step)
            if new[0] >= value - 1e-12 or t < 1e-3:
                break
            t /= 2
        u = u + t * step
        value, grad, f = new
        if np.abs(t * step).max() < 1e-9:
            break
    sa = s[:, idx]
    gain = f @ np.linalg.inv(np.eye(k) + block @ f)
    s -= sa @ gain @ sa.T  # (S⁻¹ + F)⁻¹, fine for a singular F
    m += s[:, idx] @ np.linalg.solve(s[np.ix_(idx, idx)], u - prior_m)


def _choice_step(m: np.ndarray, s: np.ndarray, items: np.ndarray, best_first: np.ndarray) -> None:
    """A pick (``best_first`` has one item) or a ranking of ``items`` under Plackett–Luce:
    each choice is the best of the items not yet placed."""
    k = len(items)
    where = {int(p): r for r, p in enumerate(items)}
    stages = []
    rest = list(range(k))
    for chosen in best_first[: k - 1]:
        stages.append((list(rest), where[int(chosen)]))
        rest.remove(where[int(chosen)])

    def loglik(u: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        value, g, f = 0.0, np.zeros(k), np.zeros((k, k))
        for rest, c in stages:
            v = u[rest]
            top = v.max()
            q = np.exp(v - top)
            total = q.sum()
            q /= total
            value += u[c] - top - math.log(total)
            g[rest] -= q
            g[c] += 1.0
            f[np.ix_(rest, rest)] += np.diag(q) - np.outer(q, q)
        return value, g, f

    _laplace(m, s, items, loglik)


_TIE_JAC = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])  # logits of i wins, j wins, tie


def _tie_step(m: np.ndarray, s: np.ndarray, i: int, j: int, nu: float) -> None:
    """ "Can't decide" between i and j under Davidson's model: it pulls their scores together,
    more so the further apart they are now."""
    lam = math.log(nu)

    def loglik(u: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        z = _TIE_JAC @ u + np.array([0.0, 0.0, lam])
        top = z.max()
        p = np.exp(z - top)
        total = p.sum()
        p /= total
        value = z[2] - top - math.log(total)
        g = _TIE_JAC.T @ (np.array([0.0, 0.0, 1.0]) - p)
        f = _TIE_JAC.T @ (np.diag(p) - np.outer(p, p)) @ _TIE_JAC
        return value, g, f

    _laplace(m, s, np.array([i, j]), loglik)


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

    def pair(self, i: int, j: int, i_won: bool) -> None:
        _update(self.m, self.s, i, j, i_won)
        self._age += 1

    def tie(self, i: int, j: int, nu: float) -> None:
        _tie_step(self.m, self.s, i, j, nu)
        self._age += 1

    def choice(self, items: np.ndarray, best_first: np.ndarray) -> None:
        _choice_step(self.m, self.s, items, best_first)
        self._age += 1


# ---------------------------------------------------------------- the simulated judge


def _answer_pair(truth, i: int, j: int, habits: Habits, scale: float, rng) -> int:
    """1 if i wins, -1 if j wins, 0 for "can't decide". ``scale`` shrinks the true gap as
    the judge tires."""
    d = (truth[i] - truth[j]) * scale
    a, b = math.exp(d / 2), math.exp(-d / 2)
    u = rng.random() * (a + b + habits.tie)
    return 1 if u < a else (-1 if u < a + b else 0)


def _answer_set(truth, items: np.ndarray, kind: str, scale: float, rng):
    """The items best first (one for a pick), under Plackett–Luce: utilities plus Gumbel
    noise, sorted (Yellott 1977)."""
    order = items[np.argsort(-(truth[items] * scale + rng.gumbel(size=len(items))))]
    return order if kind == "rank" else order[:1]


# ---------------------------------------------------------------- the cheap planner


def _pairs(order: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Candidate pairs: all of them on short lists, else each item against the next few."""
    k = len(order)
    if k <= _ALL_PAIRS:
        a, b = np.triu_indices(k, 1)
    else:
        a = np.array([x for x in range(k) for d in range(1, _WINDOW + 1) if x + d < k])
        b = np.array([x + d for x in range(k) for d in range(1, _WINDOW + 1) if x + d < k])
    return order[a], order[b]


def _plan(
    mode, order, m, s, nb, looks, draws_for, timing: Timing, kinds, rng
) -> tuple[str, np.ndarray] | None:
    """The round the cheap planner asks, as (kind, items), or None when it would stop.
    ``draws_for(fresh)`` gives posterior draws, recent or (``fresh=True``) of the current
    state. As in the real planner, sets grow from the best pair, but from one seed pair
    instead of two."""
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
    seconds = timing.seconds(closeness(mu, var))
    value = gain / seconds
    ranked = np.argsort(-value, kind="stable")
    best = ranked[:5]
    # Eight answers teach at least as much as one, so the floor can only stop the session
    # when even the best single answer teaches less than it.
    if not unseen and gain[best].max() < FLOOR_BITS:
        later = order_information_over(mu[best], var[best], FLOOR_ANSWERS)  # as the planner
        if (later * relevance[best]).max(initial=0.0) < FLOOR_BITS:
            return None
    pair = ("pair", np.array([i[best[0]], j[best[0]]]))
    set_kinds = [k for k in ("pick", "rank") if k in kinds]
    if not set_kinds or len(order) < 3:
        return pair
    region = _Region(mode, draws, everything=bool(unseen))
    seeds = [Candidate("pair", (int(i[b]), int(j[b])), 0.0, 1.0, 0.0) for b in best[:_SET_SEEDS]]
    pool = _pool(i[ranked], j[ranked])
    grown = _grow_sets(set_kinds, m, s, seeds, pool, region, timing, frozenset(), rng)
    if not grown:
        return pair
    sets = np.stack([i[best], j[best]], axis=1)
    pair_values = set_gain(m, s, sets, "rank", region.within(sets)) / seconds[best]
    top = max(grown, key=lambda c: c.value)
    if top.value > pair_values.max():
        return top.kind, np.array(top.items)
    return "pair", sets[int(np.argmax(pair_values))]


# ---------------------------------------------------------------- the forecast


class _Widths:
    """The fit's Gaussian redone for another prior width, with the same answers. The prior
    is Normal(0, width²) for every item, so the answers' precision is the fit's precision
    minus 1/width², and their pull on the scores is the fit's precision times its mean.
    Without a learned width, every simulation starts from the fit as it is."""

    def __init__(self, m0: np.ndarray, s0: np.ndarray, sigma: float | None):
        self.m0, self.s0, self.sigma = m0, s0, sigma or 1.0
        self.sd = _width_sd(s0, sigma) if sigma else 0.0
        w, v = np.linalg.eigh((s0 + s0.T) / 2)
        if self.sd:
            # Precision in the same eigenbasis; removed items make it only approximately the
            # fit's, so eigenvalues are kept positive when the width shifts them.
            self.prec, self.v = 1.0 / np.clip(w, 1e-12, None), v
            self.pull = self.prec * (v.T @ m0)  # precision times mean, in the eigenbasis
        else:
            self.root = v * np.sqrt(np.clip(w, 0.0, None))

    def draw(self, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(true scores, starting mean, starting covariance) for one simulation."""
        k = len(self.m0)
        if not self.sd:
            return self.m0 + self.root @ rng.standard_normal(k), self.m0.copy(), self.s0.copy()
        wide = self.sigma * math.exp(self.sd * rng.standard_normal())
        lam = np.clip(self.prec + 1.0 / wide**2 - 1.0 / self.sigma**2, 1e-9, None)
        m = self.v @ (self.pull / lam)
        s = (self.v / lam) @ self.v.T
        truth = m + self.v @ (rng.standard_normal(k) / np.sqrt(lam))
        return truth, m, (s + s.T) / 2


def _width_sd(s0: np.ndarray, sigma: float) -> float:
    """How unsure the prior width still is, as the sd of its log. The fit learns the width
    from the answers (an evidence maximum; MacKay 1992), so before any answers it is only
    known to its hyperprior, and true scores could spread much wider or narrower than the
    fit's. The answers pin it down by about as many items as they have settled: MacKay's
    count of well-determined parameters, n minus the posterior variance in prior units."""
    settled = max(0.0, float(len(s0) - np.trace(s0) / sigma**2))
    return 1.0 / math.sqrt(2.0 * settled + 1.0 / DEFAULT_SIGMA_PRIOR.sd**2)


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
    timing: Timing | None = None,
    kinds: tuple[str, ...] = PAIRS_ONLY,
    habits: Habits | None = None,
    effort: int = 0,
    past_efforts: Sequence[int] | None = None,
    sigma: float | None = None,
    budget_ms: float = 800.0,
    min_sims: int = 8,
    max_sims: int = 64,
    cap: int | None = None,
) -> Generator[None, None, Forecast]:
    """Rounds left until rankify stops in ``mode``, as a generator that pauses every few
    simulated rounds and returns the ``Forecast``. A terminal UI runs it between keypresses,
    so the next round never waits for it. ``active`` holds the positions of the ranked
    items, and ``looks`` how many answers each position has been in. ``timing`` and
    ``kinds`` are what the real planner uses. For fatigue, ``effort`` counts the calls the
    judge has made in the sitting under way (a ranking of k counts as k - 1), and
    ``past_efforts`` how far into its sitting each call behind the fit was made. ``sigma``
    is the prior width the fit learned, if it learned one.

    Simulations run until ``max_sims``, or until ``budget_ms`` is spent and at least
    ``min_sims`` are done. Past twice the budget, the running simulation is cut short. A
    simulation that is cut short, or still asking after ``cap`` rounds, only says "at
    least this many"; when that leaves the median unknown, the forecast is "more than"."""
    t0 = perf_counter()
    timing = timing or Timing()
    habits = habits or Habits()
    pos = np.asarray(active, dtype=np.int64)
    k = len(pos)
    cap = cap or 20 * max(k, 2)
    if k < 2:
        return Forecast(0, 0, 0, None, 0, 0, 0.0)
    m0 = np.asarray(theta, dtype=float)[pos]
    s0 = np.asarray(cov, dtype=float)[np.ix_(pos, pos)]
    looks0 = np.array([looks.get(int(p), 0) for p in pos])
    widths = _Widths(m0, s0, sigma)
    rng = np.random.default_rng([seed, 23])
    # The fit's scores reflect the judge's noise so far; without a record of sittings,
    # assume one sitting so far.
    past = habits.past_noise(range(effort) if past_efforts is None else past_efforts)
    # A round that grows sets takes a few milliseconds, so pause after each one.
    pause_every = _PAUSE_EVERY if tuple(kinds) == PAIRS_ONLY else 1

    def elapsed() -> float:
        return (perf_counter() - t0) * 1000

    done: list[float] = []  # rounds, or infinity where a simulation was cut short
    lower: list[int] = []  # rounds reached by simulations cut short: at least that many left
    while len(done) < max_sims and not (len(done) >= min_sims and elapsed() > budget_ms):
        truth, m1, s1 = widths.draw(rng)
        belief, seen = _Belief(m1, s1, rng), looks0.copy()
        m, s = belief.m, belief.s
        rounds, calls, cut = 0, effort, False
        while True:
            if rounds >= cap or (rounds % 16 == 0 and elapsed() > 2 * budget_ms):
                cut = True
                break
            order = np.argsort(-np.round(m, 9), kind="stable")
            # The real stop rules use the exact normal curve; an approximation here moved
            # the thresholds enough to stop simulations a round early, or run them long.
            nb = stop.neighbours(m, s, order)
            planned = _plan(mode, order, m, s, nb, seen, belief.draws, timing, kinds, rng)
            if planned is None:
                break
            kind, items = planned
            scale = past / habits.noise(calls)
            if kind == "pair":
                i, j = int(items[0]), int(items[1])
                said = _answer_pair(truth, i, j, habits, scale, rng)
                if said == 0:
                    belief.tie(i, j, habits.tie)
                else:
                    belief.pair(i, j, said > 0)
            else:
                belief.choice(items, _answer_set(truth, items, kind, scale, rng))
            seen[items] += 1
            calls += len(items) - 1
            rounds += 1
            if rounds % pause_every == 0:
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
