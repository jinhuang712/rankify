"""When each precision mode is done, and which items still matter for it.

A neighbour pair counts as settled when Confidence (the chance the upper item really is
better) reaches the mode's threshold, or when the two are a confident tie: at least 90%
likely to be within the tie margin of each other.
"""

import math
from dataclasses import dataclass

import numpy as np

from rankify.engine.stats import SCORE_SCALE

MODES = ("quick", "stable", "exact")
TIE_MARGIN = 30.0 / SCORE_SCALE  # 30 Score points: about a 54% win chance
TIE_CONFIDENCE = 0.9
QUICK_TOP, QUICK_NEXT = 0.9, 0.8
STABLE_LEVEL = 0.9
EXACT_LEVEL = 0.95
STABLE_TIERS = 3


def top_size(n: int) -> int:
    """How many items Stable mode puts in exact order: a quarter, at least 3."""
    return min(n, max(3, math.ceil(n / 4)))


def _cdf(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(z / math.sqrt(2.0)))


@dataclass(frozen=True)
class Neighbours:
    """For each neighbour pair in a ranking (k, k+1), best first."""

    confidence: np.ndarray  # P(item k really is better than item k+1)
    tie: np.ndarray  # P(the two are within the tie margin)

    def settled(self, level: float) -> np.ndarray:
        return (self.confidence >= level) | (self.tie >= TIE_CONFIDENCE)


def neighbours(theta: np.ndarray, cov: np.ndarray, order: list[int]) -> Neighbours:
    o = np.asarray(order, dtype=np.int64)
    if len(o) < 2:
        return Neighbours(np.zeros(0), np.zeros(0))
    upper, lower = o[:-1], o[1:]
    mu = theta[upper] - theta[lower]
    var = cov[upper, upper] + cov[lower, lower] - 2 * cov[upper, lower]
    sd = np.sqrt(np.maximum(var, 1e-18))
    confidence = _cdf(mu / sd)
    tie = _cdf((TIE_MARGIN - mu) / sd) - _cdf((-TIE_MARGIN - mu) / sd)
    return Neighbours(confidence, tie)


def target_reached(
    mode: str, nb: Neighbours, ranks: list[tuple[int, int, int]] | None = None
) -> bool:
    """Whether the mode's target holds. ``ranks`` holds (position, rank_lo, rank_hi) in
    ranking order; with it, Quick and Stable also require that no item below the part they
    settle could still be in it (its Could be range doesn't reach in)."""
    n = len(nb.confidence) + 1
    if n < 2:
        return True
    if mode == "quick":
        need = np.array([QUICK_TOP, QUICK_NEXT, QUICK_NEXT][: n - 1])
        top = nb.confidence[: len(need)]
        ordered = bool(np.all((top >= need) | (nb.tie[: len(need)] >= TIE_CONFIDENCE)))
        return ordered and _nothing_below_reaches(ranks, 3)
    if mode == "stable":
        k = top_size(n)
        if not np.all(nb.settled(STABLE_LEVEL)[: min(k, n - 1)]):
            return False
        if not all(nb.confidence[b] >= STABLE_LEVEL for b in tier_boundaries(nb, k)):
            return False
        return _nothing_below_reaches(ranks, k)
    return bool(np.all(nb.settled(EXACT_LEVEL)))


def _nothing_below_reaches(ranks: list[tuple[int, int, int]] | None, k: int) -> bool:
    """No item ranked below the top ``k`` could still be in it (Could be stays below)."""
    if ranks is None:
        return True
    return all(lo > k for _, lo, _ in ranks[k:])


def tier_boundaries(nb: Neighbours, k: int) -> list[int]:
    """Below the exact top, tiers split at the most confident gaps."""
    rest = np.arange(k, len(nb.confidence))  # neighbour pairs below the top part
    cuts = min(STABLE_TIERS, len(rest)) - 1
    if cuts <= 0:
        return []
    best = rest[np.argsort(-nb.confidence[rest], kind="stable")[:cuts]]
    return sorted(int(b) for b in best)


def in_play(mode: str, ranks: list[tuple[int, int, int]], nb: Neighbours) -> set[int]:
    """Items that still matter for the mode. ``ranks`` holds (position, rank_lo, rank_hi)
    in ranking order, best first."""
    n = len(ranks)
    if mode == "exact":
        return {p for p, _, _ in ranks}
    region = 4 if mode == "quick" else top_size(n) + 1
    play = {p for p, lo, _ in ranks if lo <= region}
    if mode == "stable":
        for b in tier_boundaries(nb, top_size(n)):
            if nb.confidence[b] < STABLE_LEVEL:
                play |= {ranks[b][0], ranks[b + 1][0]}
    return play
