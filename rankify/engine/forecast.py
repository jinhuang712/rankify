"""Rounds left, by formula: the answers each pair the mode needs will take.

A session stops when the mode's target holds (a few neighbour pairs confidently ordered or
tied, and nothing below the settled part could still reach into it; stop.py), or when no
pair is worth asking any more (the planner's floor). Both are statements about single gaps,
so the rounds left are a sum of per-pair sample sizes, the way a trial is sized for the
difference it must detect.

Which pairs those are, and how far apart, depends on the true scores, which are unknown. So
the forecast takes a fixed set of draws of them from the fit, with the prior width drawn
too while the fit is still learning it (MacKay 1992), and in each draw reads the pairs the
mode needs off the true order. Each pair then needs answers until it is done:

- The fit is a Laplace approximation (Tierney & Kadane 1986), so after n more answers at
  the judge's true rates, its estimate m of the gap solves (m - m0) / v0 = n (drive - G(m)):
  the precision now (1 / v0) times the shift equals the expected score of the answers. G is
  the score the model expects at m and ``drive`` the one the judge gives, under Davidson's
  model of wins, losses and "can't decide" (Davidson 1970). The precision becomes
  1 / v0 + n H(m), H being the slope of G. Read the other way round, n is a closed form of
  m, so walking m from today's estimate toward the true gap traces the whole path with no
  simulation. A clear judge's answers are predictable, yet each still moves an unsure
  estimate a lot; this path keeps that, where the information at the true gap would not.
- On that path the pair is done once Confidence reaches the mode's level, once it is a
  confident tie (where a tie counts), or once 8 more answers would teach it less than 0.1
  bits, weighted by how much the pair matters (the floor). The floor's bits come from a
  table computed once.
- Pairs share items, so what one pair's answers teach reaches the others through the fit's
  covariance: the answers of the pairs that settle the top are added to it in one low-rank
  update (Woodbury 1950) before the items below are counted.
- An item below the settled part is out once it is unlikely to beat whatever ends up last
  in that part: a line whose value and spread come from the draws. Against that crowd it
  is out sooner than against any one item, which matters on long lists. Its pairs matter
  only as much as the edge item belongs to the part, about the edge pair's Confidence.

The answers add up over the pairs (first looks still owed are answers too) and become
rounds: one each for pairs, about 2.5 pairs' worth for a pick or ordering (fitted on the
benchmark's mixed sessions). The judge's habits enter through their rates: how decisive
they are (sharpness), how often they can't decide, and how much noisier they get as the
sitting goes on (fatigue, averaged over the calls still to come). How the answers fall
spreads each draw's count further, by a lognormal fitted on the benchmark's sessions; the
range is the 10th to 90th percentile of that mixture.

It costs a few array operations over draws times pairs, a few milliseconds, and gives the
same answer every time. It replaced a Monte Carlo simulation of the rest of the session,
which took up to a second per forecast and would not scale to a public service; on the
benchmark's saved sessions it is as accurate or more.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
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
    order_information_over,
)

FORECAST_NAME = "formula-1"
LOW_Q, HIGH_Q = 0.1, 0.9  # the range shown: 10th to 90th percentile
DRAWS = 64  # draws of the true scores
REACH_LEVEL = 0.95  # "could still reach in": the 5% tail of the reach range stop.py uses
LUCK = 0.3  # sd of the log of the rounds a draw needs, from how the answers fall
PAIRS_PER_SET_ROUND = 2.5  # pair answers a pick or ordering of 3-5 is worth
_CAP_PER_ITEM = 50  # Exact on 20 items took about 25 rounds per item with the human judge
# How far the estimate has moved toward the true gap: fine near both ends, where the
# answers grow in proportion to the move (near 0) or to 1 / (1 - move) (near 1).
_U = np.concatenate([[0.0], np.geomspace(1e-5, 0.5, 32), 1.0 - np.geomspace(0.5, 1e-6, 32)[1:]])
_N_FLAT = np.concatenate([[0.0], np.geomspace(0.05, 4000.0, len(_U) - 1)])  # where it can't move
_REFINE = 8  # points inside the last step, to read the answers more finely

# The floor table: bits from 8 more answers to a pair, by how many standard deviations its
# gap is from zero and log10 of the gap's variance. Read with bilinear interpolation, it
# says "below the floor" as the exact sum does at all but about 1 in 1000 points.
_T_Z = np.linspace(0.0, 6.0, 121)
_T_LOGV = np.linspace(-4.0, 1.5, 56)


@dataclass(frozen=True)
class Habits:
    """How the judge answers, beyond the model. ``tie`` comes from the list's fit; fatigue
    is the benchmark's guessed human judge until a real session measures it."""

    fatigue: float = HumanParams.fatigue  # noise grows by this share per call made...
    fatigue_cap: float = HumanParams.fatigue_cap  # ...up to this multiple
    tie: float = math.exp(Prior.tie_mean)  # Davidson's nu: "can't decide" between equals
    sharpness: float = 1.0  # how much more decisive than the model expects...
    sharpness_sd: float = 0.0  # ...and how unsure that still is (sd of its log)

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

    def noise_over(self, start: float, calls: np.ndarray) -> np.ndarray:
        """The average noise over ``calls`` more calls from ``start``."""
        if self.fatigue <= 0:
            return np.ones_like(calls)
        knee = (self.fatigue_cap - 1.0) / self.fatigue

        def area(e):
            below = np.minimum(e, knee)
            return below + self.fatigue * below**2 / 2 + self.fatigue_cap * np.maximum(e - knee, 0)

        calls = np.maximum(calls, 1e-9)
        return (area(start + calls) - area(start)) / calls


@dataclass(frozen=True)
class Forecast:
    """Rounds left. ``None`` means "unknown, but more": then ``at_least`` gives a floor."""

    median: int | None
    low: int | None  # 10th percentile
    high: int | None  # 90th percentile
    at_least: int | None
    draws: int  # draws of the true scores
    capped: int  # draws that needed more than the cap
    ms: float


# ---------------------------------------------------------------- the pieces


@cache
def _floor_table() -> np.ndarray:
    z, logv = np.meshgrid(_T_Z, _T_LOGV, indexing="ij")
    v = 10.0 ** logv.ravel()
    bits = order_information_over(z.ravel() * np.sqrt(v), v, FLOOR_ANSWERS)
    return np.ascontiguousarray(bits.reshape(z.shape).ravel())


def later_bits(mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """Bits from 8 more answers to a pair whose gap is N(mu, var), from the floor table."""
    t = _floor_table()
    rows = len(_T_LOGV)
    var = np.maximum(var, 1e-12)
    fx = np.minimum(np.abs(mu) / np.sqrt(var), _T_Z[-1]) * (1.0 / (_T_Z[1] - _T_Z[0]))
    fy = np.clip(np.log10(var) - _T_LOGV[0], 0.0, _T_LOGV[-1] - _T_LOGV[0])
    fy *= 1.0 / (_T_LOGV[1] - _T_LOGV[0])
    i = np.minimum(fx.astype(np.intp), len(_T_Z) - 2)
    j = np.minimum(fy.astype(np.intp), rows - 2)
    u, w = fx - i, fy - j
    k = i * rows + j
    lo = t.take(k) + (t.take(k + rows) - t.take(k)) * u
    hi = t.take(k + 1) + (t.take(k + rows + 1) - t.take(k + 1)) * u
    return lo + (hi - lo) * w


def _phi(x: np.ndarray) -> np.ndarray:
    """The normal CDF (Abramowitz & Stegun 1964, 7.1.26; measured error under 1e-7)."""
    z = np.abs(x) / math.sqrt(2.0)
    t = 1.0 / (1.0 + 0.3275911 * z)
    poly = t * (
        0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))
    )
    return 0.5 * (1.0 + np.sign(x) * (1.0 - poly * np.exp(-z * z)))


_Z: dict[float, float] = {}


def _z(level: np.ndarray) -> np.ndarray:
    """The normal quantile of each level."""
    out = np.empty(np.shape(level))
    for lv in np.unique(level):
        if lv not in _Z:
            _Z[lv] = NormalDist().inv_cdf(float(lv))
        out[level == lv] = _Z[lv]
    return out


def score(m: np.ndarray, tie: float) -> tuple[np.ndarray, np.ndarray]:
    """Davidson's model at gap m: the expected score G (half the chance of winning minus
    that of losing) and its slope H, which is also the information of one answer."""
    a, b = np.exp(m / 2), np.exp(-m / 2)
    z = a + b + tie
    return (a - b) / (2 * z), ((a + b) * z - (a - b) ** 2) / (4 * z * z)


def _done(m, sd, z, tie_ok, rel) -> np.ndarray:
    """Whether a gap N(m, sd^2) is done: confident at quantile z, a confident tie where one
    counts, or below the floor at relevance ``rel`` (z, tie_ok and rel broadcast). ``m`` is
    already widened by the judge's sharpness, as the stopping rules see it."""
    ok = np.abs(m) >= z * sd
    if np.any(tie_ok):
        p_tie = _phi((stop.TIE_MARGIN - m) / sd) - _phi((-stop.TIE_MARGIN - m) / sd)
        ok |= tie_ok & (p_tie >= stop.TIE_CONFIDENCE)
    return ok | (rel * later_bits(m, sd * sd) < FLOOR_BITS)


def path_answers(m0, v0, d, level, tie_ok, rel, tie: float = 0.0, calibration: float = 1.0):
    """(answers, estimate, precision) at which each pair is done, for flat arrays: today's
    estimate ``m0`` of the gap and its variance ``v0``, the true gap ``d`` (in the fit's
    units, as the judge answers), the Confidence ``level`` it must reach, whether a
    confident tie counts, and how much the pair matters (``rel``, for the floor). Answers
    are infinite where the pair is never done."""
    v0 = np.maximum(v0, 1e-12)
    z = _z(level)
    answers = np.zeros(len(m0))
    m_end, prec_end = np.asarray(m0, dtype=float).copy(), 1.0 / v0
    k = calibration  # the stopping rules see the fit's gaps widened by this
    todo = np.flatnonzero(~_done(k * m0, np.sqrt(v0), z, tie_ok, rel))  # often most are done
    if len(todo) == 0:
        return answers, m_end, prec_end
    m0, v0, d, z, tie_ok, rel = m0[todo], v0[todo], d[todo], z[todo], tie_ok[todo], rel[todo]
    p0 = 1.0 / v0
    a, b = np.exp(d / 2), np.exp(-d / 2)
    drive = ((a - b) / (2 * (a + b + tie)))[:, None]
    moves = (np.abs(d - m0) > 1e-6)[:, None]
    z, tie_ok, rel = z[:, None], tie_ok[:, None], rel[:, None]

    def walk(u, flat):
        """Answers, estimate, precision and done at moves u (rows, points) toward d."""
        m = np.where(moves, m0[:, None] + (d - m0)[:, None] * u, m0[:, None])
        g, h = score(m, tie)
        with np.errstate(divide="ignore", invalid="ignore"):
            n = np.where(moves, (m - m0[:, None]) * p0[:, None] / (drive - g), flat)
        n = np.maximum.accumulate(np.nan_to_num(np.maximum(n, 0.0), nan=np.inf), axis=1)
        prec = p0[:, None] + n * h
        return n, m, prec, _done(k * m, 1.0 / np.sqrt(prec), z, tie_ok, rel)

    rows = np.arange(len(todo))
    n, m, prec, ok = walk(np.broadcast_to(_U, (len(todo), len(_U))), _N_FLAT)
    first = np.argmax(ok, axis=1)
    never = ~ok[rows, first]
    prev = np.maximum(first - 1, 0)
    # inside the last step, more finely
    t = np.linspace(0.0, 1.0, _REFINE + 1)[1:]
    u = _U[prev][:, None] + (_U[first] - _U[prev])[:, None] * t
    flat = _N_FLAT[prev][:, None] + (_N_FLAT[first] - _N_FLAT[prev])[:, None] * t
    n2, m2, prec2, ok2 = walk(u, flat)
    ok2[:, -1] = True  # the step's end is done
    k = np.argmax(ok2, axis=1)
    lo = np.where(k == 0, n[rows, prev], n2[rows, np.maximum(k - 1, 0)])
    got = np.where(first == 0, 0.0, (lo + n2[rows, k]) / 2)  # halfway, in answers
    answers[todo] = np.where(never, np.inf, got)
    m_end[todo] = np.where(first == 0, m[rows, 0], m2[rows, k])
    prec_end[todo] = np.where(first == 0, prec[rows, 0], prec2[rows, k])
    return answers, m_end, prec_end


@dataclass(frozen=True)
class _Needs:
    """For each draw, the pairs the mode needs, as places in that draw's true order."""

    upper: np.ndarray  # (draws, pairs)
    lower: np.ndarray
    level: np.ndarray  # (pairs,) the Confidence each must reach
    tie_ok: np.ndarray  # whether a confident tie settles it
    below: np.ndarray  # an item below the settled part, against the line
    rel: np.ndarray  # how much it matters, for the floor
    edge: int  # the pair across the edge of the settled part, or -1
    top: int  # how many items the mode settles
    rel_floor: float  # the least a pair below matters (Stable's tier boundaries)


def _needs(mode: str, k: int, gaps: np.ndarray) -> _Needs:
    """The pairs ``mode`` needs (stop.target_reached), read off each draw's true order.
    ``gaps`` (draws, k - 1) are the true neighbour gaps, for Stable's tier boundaries."""
    need: dict[tuple[int, int], tuple[float, bool]] = {}

    def add(a: int, b: int, level: float, tie_ok: bool) -> None:
        old = need.get((a, b))
        need[(a, b)] = (level, tie_ok) if old is None else (max(level, old[0]), tie_ok and old[1])

    draws = len(gaps)
    if mode == "quick":
        for i, level in enumerate((stop.QUICK_TOP, stop.QUICK_NEXT, stop.QUICK_NEXT)[: k - 1]):
            add(i, i + 1, level, True)
        top = min(3, k)
    elif mode == "stable":
        top = stop.top_size(k)
        for i in range(min(top, k - 1)):
            add(i, i + 1, stop.STABLE_LEVEL, True)
    else:
        for i in range(k - 1):
            add(i, i + 1, stop.EXACT_LEVEL, True)
        top = k
    for j in range(top, k):  # nothing below the settled part could still reach into it
        add(top - 1, j, REACH_LEVEL, False)
    upper = np.tile(np.array([a for a, _ in need], dtype=np.int64), (draws, 1))
    lower = np.tile(np.array([b for _, b in need], dtype=np.int64), (draws, 1))
    level = np.array([v[0] for v in need.values()])
    tie_ok = np.array([v[1] for v in need.values()])
    below = np.array([a == top - 1 and b > top for a, b in need])
    rel = np.ones(len(need))
    edge = list(need).index((top - 1, top)) if (top - 1, top) in need else -1
    if mode == "stable":
        rest = gaps[:, top:]  # tiers below the top split at the clearest gaps
        cuts = min(stop.STABLE_TIERS, rest.shape[1]) - 1
        if cuts > 0:
            at = top + np.argsort(-rest, axis=1, kind="stable")[:, :cuts]
            upper = np.concatenate([upper, at], axis=1)
            lower = np.concatenate([lower, at + 1], axis=1)
            level = np.concatenate([level, np.full(cuts, stop.STABLE_LEVEL)])
            tie_ok = np.concatenate([tie_ok, np.zeros(cuts, bool)])
            below = np.concatenate([below, np.zeros(cuts, bool)])
            rel = np.concatenate([rel, np.full(cuts, STABLE_TIER_WEIGHT)])
    floor = STABLE_TIER_WEIGHT if mode == "stable" else 0.0
    return _Needs(upper, lower, level, tie_ok, below, rel, edge, top, floor)


class _Truths:
    """True scores drawn from the fit. With a learned width, each draw also draws the width
    from what is known about it and redoes the fit's Gaussian for that width: the prior is
    Normal(0, width²) for every item, so in the covariance's eigenbasis a new width shifts
    each eigenvalue's inverse."""

    def __init__(self, m0: np.ndarray, s0: np.ndarray, sigma: float | None, rng, draws: int):
        k = len(m0)
        w, v = np.linalg.eigh((s0 + s0.T) / 2)
        prec = 1.0 / np.clip(w, 1e-12, None)
        z = rng.standard_normal((draws, k))
        if sigma:
            wide = sigma * np.exp(_width_sd(s0, sigma) * rng.standard_normal(draws))
            lam = np.clip(prec[None, :] + 1.0 / wide[:, None] ** 2 - 1.0 / sigma**2, 1e-9, None)
        else:
            lam = np.tile(prec, (draws, 1))
        pull = prec * (v.T @ m0)  # precision times mean, in the eigenbasis
        self.v, self.inv = v, 1.0 / lam
        self.mean = (pull[None, :] * self.inv) @ v.T  # (draws, k): each draw's fit
        self.truth = self.mean + (z * np.sqrt(self.inv)) @ v.T

    def cov(self) -> np.ndarray:
        """(draws, k, k): each draw's covariance."""
        return np.einsum("ie,de,je->dij", self.v, self.inv, self.v, optimize=True)


def _width_sd(s0: np.ndarray, sigma: float) -> float:
    """How unsure the prior width still is, as the sd of its log. The fit learns the width
    from the answers (an evidence maximum; MacKay 1992), so before any answers it is only
    known to its hyperprior, and true scores could spread much wider or narrower than the
    fit's. The answers pin it down by about as many items as they have settled: MacKay's
    count of well-determined parameters, n minus the posterior variance in prior units."""
    settled = max(0.0, float(len(s0) - np.trace(s0) / sigma**2))
    return 1.0 / math.sqrt(2.0 * settled + 1.0 / DEFAULT_SIGMA_PRIOR.sd**2)


def _gap_columns(M: np.ndarray, i: np.ndarray, j: np.ndarray) -> np.ndarray:
    """M's columns i minus columns j, per draw: (draws, rows, pairs)."""
    return np.take_along_axis(M, i[:, None, :], axis=2) - np.take_along_axis(
        M, j[:, None, :], axis=2
    )


def _answers(
    S, mean, truth, line, a, b, needs: _Needs, scale, tie: float, calibration: float = 1.0
) -> np.ndarray:
    """(draws, pairs) answers for each pair the mode needs. ``S`` (draws, k, k) is each
    draw's covariance, ``mean`` and ``truth`` (draws, k) its fit and true scores, ``line``
    (draws,) the true score of the last item in the settled part, ``a`` and ``b`` the items
    of each pair, ``scale`` (draws, 1) how decisive the judge is."""
    draws = len(S)
    rows = np.arange(draws)[:, None]
    n = np.zeros(a.shape)
    d = scale * (truth[rows, a] - truth[rows, b])
    est = mean[rows, a] - mean[rows, b]
    rel = np.broadcast_to(needs.rel, a.shape).copy()
    level = np.broadcast_to(needs.level, a.shape)
    tie_ok = np.broadcast_to(needs.tie_ok, a.shape)
    core = np.flatnonzero(~needs.below)
    i, j = a[:, core], b[:, core]
    now = S[rows, i, i] + S[rows, j, j] - 2 * S[rows, i, j]
    got, m_end, prec = path_answers(
        est[:, core].ravel(), now.ravel(), d[:, core].ravel(), level[:, core].ravel(),
        tie_ok[:, core].ravel(), rel[:, core].ravel(), tie, calibration,
    )  # fmt: skip
    n[:, core] = got.reshape(i.shape)
    m_end, prec = m_end.reshape(i.shape), prec.reshape(i.shape)
    # What these answers teach, added to the covariance in one low-rank (Woodbury) update:
    # precision w along each pair's gap u, so S becomes S - S U (I + W U'S U)^-1 W U'S.
    w = np.where(np.isfinite(n[:, core]), prec - 1.0 / now, 0.0)  # (draws, c)
    su = _gap_columns(S, i, j)  # S U: (draws, k, c)
    usu = _gap_columns(np.swapaxes(su, 1, 2), i, j)  # U'S U: (draws, c, c)
    eye = np.eye(len(core))[None]
    x = np.linalg.solve(eye + w[:, :, None] * usu, w[:, :, None] * np.swapaxes(su, 1, 2))
    var_after = np.diagonal(S, axis1=1, axis2=2) - np.einsum("dkc,dck->dk", su, x)
    below = needs.below
    if below.any():
        # An item is out once it is unlikely to beat whatever ends up last in the settled
        # part: a line whose value and spread now come from the draws, the spread shrinking
        # to the edge item's own as the top settles.
        spread2 = np.full(draws, float(line.std()) ** 2)
        if needs.edge >= 0:
            e = int(np.flatnonzero(core == needs.edge)[0])
            spread2 = np.minimum(spread2, var_after[np.arange(draws), a[:, needs.edge]])
            # a pair below matters as much as the edge item belongs to the settled part
            edge_conf = _phi(calibration * np.abs(m_end[:, e]) * np.sqrt(prec[:, e]))
            rel[:, below] = np.maximum(edge_conf, needs.rel_floor)[:, None]
        rb = b[:, below]
        start = float(line.mean()) - mean[rows, rb]
        now = spread2[:, None] + var_after[rows, rb]
        n[:, below] = path_answers(
            start.ravel(), now.ravel(), d[:, below].ravel(), level[:, below].ravel(),
            tie_ok[:, below].ravel(), rel[:, below].ravel(), tie, calibration,
        )[0].reshape(rb.shape)  # fmt: skip
    return n


# ---------------------------------------------------------------- the forecast


def forecast_rounds(
    mode: str,
    theta: np.ndarray,
    cov: np.ndarray,
    active: list[int],
    looks: dict[int, int],
    seed: int,
    *,
    kinds: tuple[str, ...] = PAIRS_ONLY,
    habits: Habits | None = None,
    effort: int = 0,
    past_efforts: Sequence[int] | None = None,
    sigma: float | None = None,
    cap: int | None = None,
    draws: int = DRAWS,
    calibration: float = 1.0,
    **_planner,
) -> Forecast:
    """Rounds left until rankify stops in ``mode``. ``active`` holds the positions of the
    ranked items, and ``looks`` how many answers each position has been in. ``kinds`` are
    the round kinds the list allows. For fatigue, ``effort`` counts the calls the judge has
    made in the sitting under way (a ranking of k counts as k - 1), and ``past_efforts`` how
    far into its sitting each call behind the fit was made. ``sigma`` is the prior width
    the fit learned, if it learned one. A draw that needs ``cap`` rounds or more only says
    "at least that many"; when that leaves the median unknown, the forecast is "more than".
    Other planner inputs (``timing``) are accepted and not used."""
    t0 = perf_counter()
    habits = habits or Habits()
    pos = np.asarray(active, dtype=np.int64)
    k = len(pos)
    cap = cap or _CAP_PER_ITEM * max(k, 2)
    if k < 2:
        return Forecast(0, 0, 0, None, 0, 0, 0.0)
    m0 = np.asarray(theta, dtype=float)[pos]
    s0 = np.asarray(cov, dtype=float)[np.ix_(pos, pos)]
    tr = _Truths(m0, s0, sigma, np.random.default_rng([seed, 29]), draws)
    order = np.argsort(-tr.truth, axis=1, kind="stable")  # (draws, k)
    ranked = np.take_along_axis(tr.truth, order, axis=1)
    needs = _needs(mode, k, ranked[:, :-1] - ranked[:, 1:])
    a = np.take_along_axis(order, needs.upper, axis=1)
    b = np.take_along_axis(order, needs.lower, axis=1)
    S = tr.cov()
    line = ranked[:, needs.top - 1]
    # The fit's scores already reflect the judge's noise so far; without a record of
    # sittings, assume one sitting so far.
    past = habits.past_noise(range(effort) if past_efforts is None else past_efforts)
    per_round = 1.0 if tuple(kinds) == PAIRS_ONLY else PAIRS_PER_SET_ROUND
    # Each draw takes its own sharpness from what the answers say about it so far.
    z = np.array([NormalDist().inv_cdf((q + 0.5) / draws) for q in range(draws)])
    sharp = habits.sharpness * np.exp(
        habits.sharpness_sd * np.random.default_rng([seed, 31]).permutation(z)
    )
    noise = np.full(draws, habits.noise(effort))
    n = np.zeros(a.shape)
    for _ in range(2):  # fatigue: the noise averaged over the calls still to come
        scale = (sharp * past / noise)[:, None]
        n = _answers(S, tr.mean, tr.truth, line, a, b, needs, scale, habits.tie, calibration)
        calls = np.minimum(n.sum(axis=1), cap * per_round)
        noise = habits.noise_over(float(effort), calls)
    owed = sum(max(0, MIN_LOOKS - looks.get(int(p), 0)) for p in pos)
    rounds = np.maximum(n.sum(axis=1) / per_round, owed / 2.0)  # first looks are answers too
    capped = rounds >= cap
    # How the answers fall spreads each draw's count: a lognormal around it.
    x = np.concatenate([[0.0], np.geomspace(1.0, cap, 240)])
    zero = rounds < 0.5
    safe = np.where(zero | capped, 1.0, rounds)
    t = (np.log(np.maximum(x, 0.5))[None, :] - np.log(safe)[:, None]) / LUCK
    cdf = np.where(zero[:, None], 1.0, np.where(capped[:, None], 0.0, _phi(t))).mean(axis=0)

    def quantile(q: float) -> int | None:
        at = np.flatnonzero(cdf >= q)
        return None if len(at) == 0 else math.ceil(x[at[0]])

    median = quantile(0.5)
    return Forecast(
        median=median,
        low=quantile(LOW_Q),
        high=quantile(HIGH_Q),
        at_least=int(cap) if median is None else None,
        draws=draws,
        capped=int(capped.sum()),
        ms=(perf_counter() - t0) * 1000,
    )
