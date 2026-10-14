"""Choosing the next round.

rankify asks the pair whose answer is expected to teach the most about the *order* per
second of the judge's time, among the items that still matter for the current mode.

"Teach the most" is the mutual information between the answer and which of the two items
is really better: I(answer; sign(theta_i - theta_j)), in the spirit of BALD (Houlsby et al.
2011). Plain BALD measures information about the scores themselves, so it keeps asking
pairs whose order is settled just to sharpen the size of their gap. For a ranking only the
order matters. A pair whose order is already known teaches nothing, and so does a pair the
model knows is a tie, even though its answer is a coin flip. Baselines use ``random_pair``.
"""

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cache
from statistics import NormalDist

import numpy as np

from rankify.engine import stop
from rankify.engine.model import A_WINS, K_MAX, TIE

PLANNER_NAME = "order-info-pair-0.2"
MIXED_PLANNER_NAME = "order-info-mixed-0.3"  # pairs, picks and rankings
# Whether a pair the judge has answered may be asked again. The model treats every answer as
# a fresh coin flip, so a close pair always looks worth asking again, and 24-51% of Quick
# rounds were repeats; but a person remembers and answers the same way. "contradicted": only
# when the fit now orders the pair against the judge's own answers on it; "once": one
# re-check of any pair; both at most MAX_ASKS times in all. Both cut sessions by about half
# but left judges who slip with their slips (experiments/2026-10-14-step4-fit-and-repeats.md),
# so the default stays "always" until the stop rules are redone.
ASK_AGAIN = "always"
MAX_ASKS = 2
# Stop when even FLOOR_ANSWERS more answers to the most useful pair would teach less than
# FLOOR_BITS about the order that matters. Judged over several answers, not one: a judge
# who gets a pair right 60% of the time teaches only 0.03 bits per answer, but it adds up.
FLOOR_ANSWERS = 8
FLOOR_BITS = 0.1
# Fixed standard-normal quantiles: a deterministic average over the posterior of a gap.
_NODES = np.array([NormalDist().inv_cdf((k + 0.5) / 64) for k in range(64)])
MAX_ALL_PAIRS = 60  # above this many items, only pair each item with its nearest scores
NEAREST = 8
_LOGISTIC_TO_PROBIT = 1 / 1.702  # sigmoid(x) ~ Phi(x / 1.702)
_C = math.sqrt(math.pi * math.log(2) / 2)


def derive_seed(*parts: int) -> int:
    """A 63-bit seed from integer parts, so it fits in a SQLite INTEGER."""
    state = np.random.SeedSequence([int(p) for p in parts]).generate_state(1, dtype=np.uint64)
    return int(state[0] >> np.uint64(1))


def random_pair(candidates: np.ndarray, seed: int) -> tuple[int, int]:
    """Two different candidates, in random display order."""
    if len(candidates) < 2:
        raise ValueError("need at least two items to make a pair")
    rng = np.random.default_rng(seed)
    first, second = rng.choice(np.asarray(candidates), size=2, replace=False)
    return int(first), int(second)


# ---------------------------------------------------------------- information gain


def _entropy_bits(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-15, 1 - 1e-15)
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


def _phi(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def bald(mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """Expected information (bits) from asking "is i better than j?", for score differences
    with posterior mean ``mu`` and variance ``var``. Closed form for a probit model, which
    matches our logistic curve closely (Houlsby et al. 2011)."""
    m = np.asarray(mu) * _LOGISTIC_TO_PROBIT
    s2 = np.asarray(var) * _LOGISTIC_TO_PROBIT**2
    answer_entropy = _entropy_bits(_phi(m / np.sqrt(1 + s2)))
    expected_noise = _C / np.sqrt(s2 + _C**2) * np.exp(-(m**2) / (2 * (s2 + _C**2)))
    return np.maximum(answer_entropy - expected_noise, 0.0)


def order_information(mu: np.ndarray, var: np.ndarray, nodes: np.ndarray = _NODES) -> np.ndarray:
    """Expected information (bits) about which item is better, from asking the pair once.

    ``mu`` and ``var`` describe the posterior of each gap theta_i - theta_j. The answer
    follows the logistic curve of the gap. Averaged over 64 fixed posterior quantiles, or
    over ``nodes`` (standard-normal quantiles) where speed matters more.
    """
    d = np.asarray(mu)[:, None] + np.sqrt(np.asarray(var))[:, None] * nodes[None, :]
    p_first = 1.0 / (1.0 + np.exp(-d))
    upper = d > 0
    joint = np.stack(
        [
            np.mean(p_first * upper, axis=1),  # first wins, first really better
            np.mean(p_first * ~upper, axis=1),  # first wins, second really better
            np.mean((1 - p_first) * upper, axis=1),
            np.mean((1 - p_first) * ~upper, axis=1),
        ],
        axis=1,
    )
    p_answer = np.stack([joint[:, 0] + joint[:, 1], joint[:, 2] + joint[:, 3]], axis=1)
    p_order = np.stack([joint[:, 0] + joint[:, 2], joint[:, 1] + joint[:, 3]], axis=1)
    product = p_answer[:, [0, 0, 1, 1]] * p_order[:, [0, 1, 0, 1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(joint > 0, joint * np.log2(joint / product), 0.0)
    return np.maximum(terms.sum(axis=1), 0.0)


def order_information_over(
    mu: np.ndarray, var: np.ndarray, answers: int, nodes: np.ndarray = _NODES
) -> np.ndarray:
    """Expected information (bits) about which item is better from ``answers`` more answers to
    the same pair. One answer from a judge who gets a pair right 60% of the time teaches at
    most 0.03 bits, but those bits add up, so this is the right test for "worth asking"."""
    d = np.asarray(mu)[:, None] + np.sqrt(np.asarray(var))[:, None] * nodes[None, :]
    p = 1.0 / (1.0 + np.exp(-d))  # (pairs, nodes)
    s = np.arange(answers + 1)
    comb = np.array([math.comb(answers, int(k)) for k in s], dtype=float)
    # P(first wins s times | gap), shape (pairs, nodes, answers + 1)
    likelihood = comb * p[..., None] ** s * (1 - p[..., None]) ** (answers - s)
    upper = (d > 0)[..., None]
    joint = np.stack([np.mean(likelihood * upper, axis=1), np.mean(likelihood * ~upper, axis=1)])
    p_count = joint.sum(axis=0)  # (pairs, answers + 1)
    p_order = joint.sum(axis=2)  # (2, pairs)
    product = p_count[None, :, :] * p_order[:, :, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(joint > 0, joint * np.log2(joint / product), 0.0)
    return np.maximum(terms.sum(axis=(0, 2)), 0.0)


def closeness(mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """How hard the pair looks: 0 for a coin flip, larger for an easy call (probit margin)."""
    m = np.abs(np.asarray(mu)) * _LOGISTIC_TO_PROBIT
    return m / np.sqrt(1 + np.asarray(var) * _LOGISTIC_TO_PROBIT**2)


# ---------------------------------------------------------------- time per answer


# Seconds for a pick or rank round, as a multiple of the judge's typical pair, until the
# judge's own times for that kind and size are known. These are guesses: ranking k items
# takes about as long as their k - 1 neighbour calls, and picking the best of k is closer
# to one hard call plus a quick scan of the rest.
SET_TIME_GUESS = {
    ("pick", 3): 1.33,
    ("pick", 4): 1.67,
    ("pick", 5): 2.0,
    ("rank", 3): 2.0,
    ("rank", 4): 3.0,
    ("rank", 5): 4.33,
}
MIN_SET_SAMPLES = 8  # timed answers of one kind and size before they replace the guess


@dataclass(frozen=True)
class Timing:
    """Expected seconds for a pair: base + close * exp(-closeness / width), from the
    judge's own answer times (close calls take longer; Moyer & Landauer 1967). Pick and
    rank rounds use the judge's median for that kind and size once there are enough."""

    base: float = 3.0
    close: float = 0.0
    width: float = 0.5
    samples: int = 0
    typical: float = 3.0  # median seconds per pair
    sets: tuple[tuple[str, int, float, int], ...] = ()  # (kind, size, median seconds, answers)

    def seconds(self, margin: np.ndarray) -> np.ndarray:
        return self.base + self.close * np.exp(-np.asarray(margin) / self.width)

    def set_seconds(self, kind: str, size: int) -> float:
        for k, s, sec, count in self.sets:
            if (k, s) == (kind, size) and count >= MIN_SET_SAMPLES:
                return sec
        return SET_TIME_GUESS[(kind, size)] * self.typical

    @staticmethod
    def fit(
        samples: Sequence[tuple[float, float]], set_samples: Sequence[tuple[str, int, float]] = ()
    ) -> "Timing":
        """``samples``: (closeness when asked, seconds taken) for pairs; needs 20 to fit the
        curve. ``set_samples``: (kind, size, seconds) for pick and rank rounds."""
        good = [(z, s) for z, s in samples if 0.2 < s < 60.0]
        groups: dict[tuple[str, int], list[float]] = {}
        for kind, size, sec in set_samples:
            if 0.2 < sec < 180.0:
                groups.setdefault((kind, size), []).append(sec)
        sets = tuple((k, s, float(np.median(v)), len(v)) for (k, s), v in sorted(groups.items()))
        if len(good) < 20:
            if good:
                med = float(np.median([s for _, s in good]))
                return Timing(base=med, samples=len(good), typical=med, sets=sets)
            return Timing(sets=sets)
        z, sec = (np.array(v) for v in zip(*good, strict=True))
        typical = float(np.median(sec))
        x = np.exp(-z / Timing.width)
        design = np.stack([np.ones_like(x), x], 1)
        (base, close), *_ = np.linalg.lstsq(design, sec, rcond=None)
        if base <= 0.2 or close < 0:
            return Timing(base=typical, samples=len(good), typical=typical, sets=sets)
        return Timing(
            base=float(base), close=float(close), samples=len(good), typical=typical, sets=sets
        )


# ---------------------------------------------------------------- the plan


@dataclass(frozen=True)
class Candidate:
    kind: str  # "pair", "pick" or "rank"
    items: tuple[int, ...]  # positions of the items, in display order
    gain: float  # bits
    seconds: float
    value: float  # bits per second
    confidence: float | None = None  # pairs: P(first is better), before asking
    closeness: float | None = None  # pairs

    @property
    def first(self) -> int:
        return self.items[0]

    @property
    def second(self) -> int:
        return self.items[1]


@dataclass(frozen=True)
class Plan:
    chosen: Candidate | None  # None: stop
    candidates: list[Candidate]  # the best few, for `rankify why`
    # "first look", "best value", "another look", "target reached" or "nothing worth asking"
    reason: str
    in_play: int


MIN_LOOKS = 2  # answers about an item before the planner may judge it unimportant
# Before the floor may stop a session, every item still in play gets this many answers.
# On a long list the chance of belonging to the top is spread thinly over many barely
# seen items, so no single pair looks worth asking even while who belongs there is
# still open (on 50-item Quick lists the floor stopped with the top 3 wrong in half).
TOPUP_LOOKS = 6
# How the planner scores pairs. "time" is rankify: order information per second. The
# others exist only to check that choice in the benchmark: "per-round" ignores time,
# and "closest" asks the relevant pair closest to 50/50 (uncertainty sampling) in place
# of order information. Stopping is the same for all three.
VARIANTS = ("time", "per-round", "closest")
PAIRS_ONLY = ("pair",)
ALL_KINDS = ("pair", "pick", "rank")


def plan_pair(
    mode: str,
    theta: np.ndarray,
    cov: np.ndarray,
    ranks: list[tuple[int, int, int]],
    timing: Timing,
    seed: int,
    looks: dict[int, int] | None = None,
) -> Plan:
    """The next pair for ``mode``: ``plan_round`` with pairs only."""
    return plan_round(mode, theta, cov, ranks, timing, seed, looks, PAIRS_ONLY)


def answered_pairs(history) -> dict[tuple[int, int], tuple[int, int]]:
    """For each pair asked so far, keyed lower position first: (the lower position's wins
    minus the other's, times asked). "Can't decide" counts as asked, for neither side."""
    out: dict[tuple[int, int], tuple[int, int]] = {}
    for a, b, y in history:
        key = (min(a, b), max(a, b))
        net, asks = out.get(key, (0, 0))
        if y != TIE:
            winner = a if y == A_WINS else b
            net += 1 if winner == key[0] else -1
        out[key] = (net, asks + 1)
    return out


def _askable(i: np.ndarray, j: np.ndarray, theta: np.ndarray, answered) -> np.ndarray:
    """Which of the pairs (i, j) may be asked: any pair not asked yet, and a pair asked before
    only when the fit now puts it in the opposite order to the judge's own answers on it."""
    keep = np.ones(len(i), dtype=bool)
    if not answered or ASK_AGAIN == "always":
        return keep
    for k, (p, q) in enumerate(zip(i.tolist(), j.tolist(), strict=True)):
        key = (p, q) if p < q else (q, p)
        seen = answered.get(key)
        if seen is not None:
            net, asks = seen
            contradicted = net * (theta[key[0]] - theta[key[1]]) < 0
            # "once": any pair may get one re-check when it is worth asking; else only
            # a contradicted pair may
            keep[k] = (ASK_AGAIN == "once" or contradicted) and asks < MAX_ASKS
    return keep


def plan_round(
    mode: str,
    theta: np.ndarray,
    cov: np.ndarray,
    ranks: list[tuple[int, int, int]],
    timing: Timing,
    seed: int,
    looks: dict[int, int] | None = None,
    kinds: tuple[str, ...] = ALL_KINDS,
    avoid: frozenset = frozenset(),
    variant: str = "time",
    answered: dict | None = None,
) -> Plan:
    """The next round for ``mode``. ``ranks`` holds (position, rank_lo, rank_hi) for the
    active items, best first. ``looks`` counts the answers that involved each item.
    ``kinds`` are the round kinds allowed; ``avoid`` holds sets (as frozensets of positions)
    not to show again, because the judge couldn't decide on them. ``answered`` holds the
    pairs asked so far (see ``answered_pairs``); they are asked again only as ``_askable``
    allows.

    Every item first gets ``MIN_LOOKS`` answers. An item that has barely been compared sits
    in the middle of the ranking with a wide range, so without this it could be ignored even
    when it is really the best one.

    Pairs are ranked by their exact order information. Pick and rank rounds are grown from
    the best pairs, one item at a time, and scored with ``set_gain``; the best pairs are
    scored the same way, so every kind competes on one scale. When to stop is decided on
    pairs alone, exactly as with pairs only.
    """
    order = [p for p, _, _ in ranks]
    looks = looks or {}
    unseen = sorted((looks.get(p, 0), p) for p in order if looks.get(p, 0) < MIN_LOOKS)
    nb = stop.neighbours(theta, cov, order)
    play = stop.in_play(mode, ranks, nb)
    if not unseen and stop.target_reached(mode, nb, ranks):
        return Plan(None, [], "target reached", len(play))
    if unseen:  # a first look: the least-seen item against its most informative partner
        newcomer = unseen[0][1]
        others = np.array([p for p in order if p != newcomer])
        i, j = np.full(len(others), newcomer), others
        reason = "first look"
    else:
        i, j = _candidate_pairs(order, play)
        reason = "best value"
    keep = _askable(i, j, theta, answered)
    i, j = i[keep], j[keep]
    if len(i) == 0:
        return Plan(None, [], "nothing worth asking", len(play))
    region = _Region(mode, theta, cov, order, seed, everything=bool(unseen))
    mu = theta[i] - theta[j]
    var = np.maximum(cov[i, i] + cov[j, j] - 2 * cov[i, j], 1e-12)
    relevance = region.pairs(i, j)
    gain = order_information(mu, var) * relevance
    margin = closeness(mu, var)
    seconds = timing.seconds(margin)
    value = gain / seconds
    if variant == "per-round":
        value = gain
    elif variant == "closest":  # 1 for a coin flip, falling as the answer gets predictable
        value = relevance * 2.0 * (1.0 - _phi(margin))
    ranked = np.argsort(-value, kind="stable")
    best = ranked[:5]
    rng = np.random.default_rng(seed)
    candidates = []
    for k in best:
        a, b = (int(i[k]), int(j[k])) if rng.random() < 0.5 else (int(j[k]), int(i[k]))
        d = theta[a] - theta[b]
        candidates.append(
            Candidate(
                "pair",
                (a, b),
                float(gain[k]),
                float(seconds[k]),
                float(value[k]),
                float(_phi(np.array(d / math.sqrt(var[k] + 1e-18)))),
                float(margin[k]),
            )
        )
    if not unseen:
        later = order_information_over(mu[best], var[best], FLOOR_ANSWERS) * relevance[best]
        if later.max(initial=0.0) < FLOOR_BITS:
            look = _another_look(order, play, looks, theta, cov, region, timing, rng, answered)
            if look is not None:
                return Plan(look, [look], "another look", len(play))
            return Plan(None, candidates, "nothing worth asking", len(play))
    set_kinds = [k for k in ("pick", "rank") if k in kinds]
    if set_kinds and len(order) >= 3:
        pool = _pool(i[ranked], j[ranked])
        grown = _grow_sets(set_kinds, theta, cov, candidates, pool, region, timing, avoid, rng)
        if grown:
            pairs = [_rescored(c, theta, cov, region) for c in candidates]
            everything = sorted(pairs + grown, key=lambda c: -c.value)[:5]
            return Plan(everything[0], everything, reason, len(play))
    return Plan(candidates[0], candidates, reason, len(play))


def _another_look(
    order, play, looks, theta, cov, region, timing, rng, answered=None
) -> Candidate | None:
    """When the floor would stop: the least-seen item still in play, if it has fewer than
    TOPUP_LOOKS answers, against the partner whose answer is worth most per second, among
    the partners it may still be asked about."""
    short = sorted((looks.get(p, 0), p) for p in play if looks.get(p, 0) < TOPUP_LOOKS)
    for _, new in short:
        others = np.array([q for q in order if q != new])
        i, j = np.full(len(others), new), others
        keep = _askable(i, j, theta, answered)
        if np.any(keep):
            i, j = i[keep], j[keep]
            break
    else:
        return None
    mu = theta[i] - theta[j]
    var = np.maximum(cov[i, i] + cov[j, j] - 2 * cov[i, j], 1e-12)
    margin = closeness(mu, var)
    gain = order_information(mu, var) * region.pairs(i, j)
    seconds = timing.seconds(margin)
    k = int(np.argmax(gain / seconds))
    a, b = (int(i[k]), int(j[k])) if rng.random() < 0.5 else (int(j[k]), int(i[k]))
    confidence = float(_phi(np.array((theta[a] - theta[b]) / math.sqrt(var[k] + 1e-18))))
    return Candidate(
        "pair",
        (a, b),
        float(gain[k]),
        float(seconds[k]),
        float(gain[k] / seconds[k]),
        confidence,
        float(margin[k]),
    )


# ---------------------------------------------------------------- pick and rank rounds

SET_SEEDS = 2  # grow sets from this many of the best pairs
SET_POOL = 12  # a set draws its items from the items of the best pairs, up to this many
_GH_X, _GH_W = np.polynomial.hermite.hermgauss(16)
_GH_NODES = math.sqrt(2.0) * _GH_X  # standard-normal quadrature nodes...
_GH_WEIGHTS = _GH_W / math.sqrt(math.pi)  # ...and weights


def _probit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-1.702 * x))  # Phi(x), to within 0.01


@cache
def _rank_layout(k: int) -> np.ndarray:
    """Every order of k items, as rows of positions."""
    return np.array(list(itertools.permutations(range(k))), dtype=np.int64)


def _fisher(mu: np.ndarray, kind: str) -> np.ndarray:
    """Expected Fisher information of one answer about the shown items' scores, at ``mu``
    (sets, k). A pick is one softmax choice; a full order is k - 1 of them, averaged over
    every order the judge could give under Plackett-Luce. Each stage's choice probabilities
    are laid out by item, so averaging a stage's diag(q) - q qᵀ over the orders is one
    small matrix product."""
    c, k = mu.shape
    if kind == "pick" or k == 2:
        q = np.exp(mu - mu.max(axis=1, keepdims=True))
        q /= q.sum(axis=1, keepdims=True)
        return q[:, :, None] * np.eye(k) - q[:, :, None] * q[:, None, :]
    perms = _rank_layout(k)
    orders = np.arange(len(perms))[:, None]
    log_p = np.zeros((c, len(perms)))
    by_item = []
    for r in range(k - 1):
        rest = perms[:, r:]  # (orders, m): the items not yet placed
        u = mu[:, rest]  # (sets, orders, m)
        top = u.max(axis=2, keepdims=True)
        q = np.exp(u - top)
        total = q.sum(axis=2, keepdims=True)
        q /= total
        log_p += u[:, :, 0] - (top + np.log(total))[:, :, 0]
        full = np.zeros((c, len(perms), k))
        full[:, orders, rest] = q
        by_item.append(full)
    p = np.exp(log_p)  # P(order) for each set
    f = np.zeros((c, k, k))
    for full in by_item:
        weighted = full * p[:, :, None]
        f += weighted.sum(axis=1)[:, :, None] * np.eye(k)
        f -= weighted.transpose(0, 2, 1) @ full
    return f


def set_gain(
    theta: np.ndarray, cov: np.ndarray, sets: np.ndarray, kind: str, relevance: np.ndarray
) -> np.ndarray:
    """Expected information (bits) from one answer about the order of the shown items,
    weighted by ``relevance`` (sets, k, k) for each pair.

    The order of a set is fixed by its neighbours: once A > B and B > C are known, A > C
    follows. So only pairs that are neighbours in the set's current order count. Counting
    every pair would count the same information about twice for an uncertain set of five;
    counting neighbours comes within about 25% of the exact information about the whole
    order (from posterior draws), on the low side, and is exact for a pair.

    Each pair's part is a cheap Gaussian estimate (within about 20% of the exact value):
    the answer's expected Fisher information shrinks the covariance of the set (a Laplace
    update; MacKay 1992), and the pair's gap mean moves by the spread that update implies.
    For a pair the result is close to ``order_information``.
    """
    sets = np.asarray(sets, dtype=np.int64)
    k = sets.shape[1]
    mu = theta[sets]
    s = cov[sets[:, :, None], sets[:, None, :]]
    f = _fisher(mu, kind)
    after = s - s @ f @ np.linalg.solve(np.eye(k) + s @ f, s)
    a, b = np.triu_indices(k, 1)
    m = mu[:, a] - mu[:, b]
    v = np.maximum(s[:, a, a] + s[:, b, b] - 2 * s[:, a, b], 1e-12)
    v2 = np.clip(after[:, a, a] + after[:, b, b] - 2 * after[:, a, b], 1e-12, v)
    before = _entropy_bits(_probit(m / np.sqrt(v)))
    moved = m[..., None] + np.sqrt(v - v2)[..., None] * _GH_NODES
    later = _entropy_bits(_probit(moved / np.sqrt(v2)[..., None])) @ _GH_WEIGHTS
    place = np.argsort(np.argsort(-mu, axis=1, kind="stable"), axis=1)  # 0 = best now
    neighbours = np.abs(place[:, a] - place[:, b]) == 1
    return np.sum(relevance[:, a, b] * neighbours * np.maximum(before - later, 0.0), axis=1)


def _pool(i: np.ndarray, j: np.ndarray) -> list[int]:
    """Items of the best pairs, best pair first, up to SET_POOL of them."""
    pool: list[int] = []
    for p in np.stack([i, j], axis=1).ravel():
        if int(p) not in pool:
            pool.append(int(p))
            if len(pool) == SET_POOL:
                break
    return pool


def _confident_ties(theta: np.ndarray, cov: np.ndarray, items: list[int]) -> set[frozenset]:
    """Pairs the model already holds to be a tie: a set never shows both, because ordering
    them would cost the judge time and teach nothing."""
    out = set()
    for x, y in itertools.combinations(items, 2):
        mu = theta[x] - theta[y]
        sd = math.sqrt(max(cov[x, x] + cov[y, y] - 2 * cov[x, y], 1e-18))
        tie = NormalDist().cdf((stop.TIE_MARGIN - mu) / sd) - NormalDist().cdf(
            (-stop.TIE_MARGIN - mu) / sd
        )
        if tie >= stop.TIE_CONFIDENCE:
            out.add(frozenset((x, y)))
    return out


def _grow_sets(kinds, theta, cov, pairs, pool, region, timing, avoid, rng) -> list[Candidate]:
    """Pick and rank rounds of 3 to K_MAX items, each grown from one of the best pairs by
    adding the item that adds the most information."""
    ties = _confident_ties(theta, cov, pool)
    found: dict[tuple[str, frozenset], Candidate] = {}
    for kind in kinds:
        for start in pairs[:SET_SEEDS]:
            current = list(start.items)
            for size in range(3, K_MAX + 1):
                adds = [
                    x
                    for x in pool
                    if x not in current and not any(frozenset((x, y)) in ties for y in current)
                ]
                if not adds:
                    break
                sets = np.array([current + [x] for x in adds], dtype=np.int64)
                gains = set_gain(theta, cov, sets, kind, region.within(sets))
                gains[[frozenset(map(int, s)) in avoid for s in sets]] = -np.inf
                best = int(np.argmax(gains))
                if not np.isfinite(gains[best]):
                    break
                current = [int(v) for v in sets[best]]
                seconds = timing.set_seconds(kind, size)
                shown = tuple(int(v) for v in rng.permutation(current))
                c = Candidate(kind, shown, float(gains[best]), seconds, gains[best] / seconds)
                found.setdefault((kind, frozenset(current)), c)
    return list(found.values())


def _rescored(c: Candidate, theta, cov, region) -> Candidate:
    """A pair candidate scored the way sets are, so the two compare fairly."""
    sets = np.array([c.items], dtype=np.int64)
    gain = float(set_gain(theta, cov, sets, "rank", region.within(sets))[0])
    return replace(c, gain=gain, value=gain / c.seconds)


# ---------------------------------------------------------------- what matters for the mode

RELEVANCE_DRAWS = 256
STABLE_TIER_WEIGHT = 0.25  # Stable also needs tier boundaries below the exact top


class _Region:
    """How much the order of two items matters for the mode's target: the chance, over
    posterior draws, that either item really belongs to the part of the ranking the mode
    settles. Exact mode, and first looks, count every pair fully."""

    def __init__(self, mode, theta, cov, order, seed, everything: bool = False):
        self.mode = mode
        self.top = None
        if everything or mode == "exact":
            return
        pos = np.asarray(order)
        n = len(pos)
        region = 3 if mode == "quick" else stop.top_size(n) + 1
        sub = cov[np.ix_(pos, pos)]
        try:
            chol = np.linalg.cholesky(sub + 1e-12 * np.eye(n))
        except np.linalg.LinAlgError:
            w, v = np.linalg.eigh(sub)
            chol = v * np.sqrt(np.clip(w, 0.0, None))
        z = np.random.default_rng([seed, 11]).standard_normal((RELEVANCE_DRAWS, n))
        draws = theta[pos] + z @ chol.T
        ranks = np.empty_like(draws, dtype=np.int64)
        ranks[np.arange(RELEVANCE_DRAWS)[:, None], np.argsort(-draws, axis=1)] = np.arange(1, n + 1)
        self.top = np.zeros((RELEVANCE_DRAWS, len(theta)), dtype=bool)
        self.top[:, pos] = ranks <= region

    def _floor(self, rel: np.ndarray) -> np.ndarray:
        return np.maximum(rel, STABLE_TIER_WEIGHT) if self.mode == "stable" else rel

    def pairs(self, i: np.ndarray, j: np.ndarray) -> np.ndarray:
        if self.top is None:
            return np.ones(len(i))
        return self._floor(np.mean(self.top[:, i] | self.top[:, j], axis=0))

    def within(self, sets: np.ndarray) -> np.ndarray:
        """(sets, k, k): the weight of each pair inside each set."""
        c, k = sets.shape
        if self.top is None:
            return np.ones((c, k, k))
        t = self.top[:, sets]  # (draws, sets, k)
        return self._floor(np.mean(t[..., :, None] | t[..., None, :], axis=0))


def _candidate_pairs(order: list[int], play: set[int]):
    """Pairs with at least one item that still matters, as two position arrays."""
    pos = np.array(order)
    if len(pos) <= MAX_ALL_PAIRS:
        a, b = np.triu_indices(len(pos), 1)
        i, j = pos[a], pos[b]
    else:  # each item against its nearest neighbours in the current ranking
        pairs = {
            (min(pos[x], pos[y]), max(pos[x], pos[y]))
            for x in range(len(pos))
            for y in range(x + 1, min(len(pos), x + 1 + NEAREST))
        }
        i, j = (np.array(v) for v in zip(*sorted(pairs), strict=True))
    keep = np.array([(p in play) or (q in play) for p, q in zip(i, j, strict=True)], dtype=bool)
    return i[keep], j[keep]
