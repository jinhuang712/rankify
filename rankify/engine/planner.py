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

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from rankify.engine import stop

PLANNER_NAME = "order-info-pair-0.2"
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


def order_information(mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """Expected information (bits) about which item is better, from asking the pair once.

    ``mu`` and ``var`` describe the posterior of each gap theta_i - theta_j. The answer
    follows the logistic curve of the gap. Averaged over 64 fixed posterior quantiles.
    """
    d = np.asarray(mu)[:, None] + np.sqrt(np.asarray(var))[:, None] * _NODES[None, :]
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


def order_information_over(mu: np.ndarray, var: np.ndarray, answers: int) -> np.ndarray:
    """Expected information (bits) about which item is better from ``answers`` more answers to
    the same pair. One answer from a judge who gets a pair right 60% of the time teaches at
    most 0.03 bits, but those bits add up, so this is the right test for "worth asking"."""
    d = np.asarray(mu)[:, None] + np.sqrt(np.asarray(var))[:, None] * _NODES[None, :]
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


@dataclass(frozen=True)
class Timing:
    """Expected seconds for a pair: base + close * exp(-closeness / width), from the
    judge's own answer times (close calls take longer; Moyer & Landauer 1967)."""

    base: float = 3.0
    close: float = 0.0
    width: float = 0.5
    samples: int = 0

    def seconds(self, margin: np.ndarray) -> np.ndarray:
        return self.base + self.close * np.exp(-np.asarray(margin) / self.width)

    @staticmethod
    def fit(samples: list[tuple[float, float]]) -> "Timing":
        """``samples``: (closeness when asked, seconds taken). Needs 20 to use them."""
        good = [(z, s) for z, s in samples if 0.2 < s < 60.0]
        if len(good) < 20:
            if good:
                return Timing(base=float(np.median([s for _, s in good])), samples=len(good))
            return Timing()
        z, sec = (np.array(v) for v in zip(*good, strict=True))
        x = np.exp(-z / Timing.width)
        design = np.stack([np.ones_like(x), x], 1)
        (base, close), *_ = np.linalg.lstsq(design, sec, rcond=None)
        if base <= 0.2 or close < 0:
            return Timing(base=float(np.median(sec)), samples=len(good))
        return Timing(base=float(base), close=float(close), samples=len(good))


# ---------------------------------------------------------------- the plan


@dataclass(frozen=True)
class Candidate:
    first: int  # position of the item to show first
    second: int
    gain: float  # bits
    seconds: float
    value: float  # bits per second
    confidence: float  # P(first is better), before asking
    closeness: float


@dataclass(frozen=True)
class Plan:
    chosen: Candidate | None  # None: stop
    candidates: list[Candidate]  # the best few, for `rankify why`
    reason: str  # "best value", "target reached" or "nothing worth asking"
    in_play: int


MIN_LOOKS = 2  # answers about an item before the planner may judge it unimportant


def plan_pair(
    mode: str,
    theta: np.ndarray,
    cov: np.ndarray,
    ranks: list[tuple[int, int, int]],
    timing: Timing,
    seed: int,
    looks: dict[int, int] | None = None,
) -> Plan:
    """The next pair for ``mode``. ``ranks`` holds (position, rank_lo, rank_hi) for the active
    items, best first. ``looks`` counts the answers that involved each item.

    Every item first gets ``MIN_LOOKS`` answers. An item that has barely been compared sits
    in the middle of the ranking with a wide range, so without this it could be ignored even
    when it is really the best one.
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
    if len(i) == 0:
        return Plan(None, [], "nothing worth asking", len(play))
    mu = theta[i] - theta[j]
    var = np.maximum(cov[i, i] + cov[j, j] - 2 * cov[i, j], 1e-12)
    relevance = np.ones(len(i)) if unseen else _relevance(mode, theta, cov, order, i, j, seed)
    gain = order_information(mu, var) * relevance
    margin = closeness(mu, var)
    seconds = timing.seconds(margin)
    value = gain / seconds
    best = np.argsort(-value, kind="stable")[:5]
    rng = np.random.default_rng(seed)
    candidates = []
    for k in best:
        a, b = (int(i[k]), int(j[k])) if rng.random() < 0.5 else (int(j[k]), int(i[k]))
        d = theta[a] - theta[b]
        candidates.append(
            Candidate(
                a,
                b,
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
            return Plan(None, candidates, "nothing worth asking", len(play))
    return Plan(candidates[0], candidates, reason, len(play))


RELEVANCE_DRAWS = 256
STABLE_TIER_WEIGHT = 0.25  # Stable also needs tier boundaries below the exact top


def _relevance(mode, theta, cov, order, i, j, seed) -> np.ndarray:
    """How much each pair's order matters for the mode's target: the chance, over posterior
    draws, that either item really belongs to the part of the ranking the mode settles."""
    if mode == "exact":
        return np.ones(len(i))
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
    top = ranks <= region
    where = {int(p): k for k, p in enumerate(pos)}
    a = np.array([where[int(p)] for p in i])
    b = np.array([where[int(p)] for p in j])
    rel = np.mean(top[:, a] | top[:, b], axis=0)
    if mode == "stable":
        rel = np.maximum(rel, STABLE_TIER_WEIGHT)
    return rel


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
