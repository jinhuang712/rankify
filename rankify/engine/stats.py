"""What the screen shows: Score, Confidence and Could be, derived from a fit."""

import math
from dataclasses import dataclass

import numpy as np

# Elo points per natural-log unit: 400 / ln 10.
SCORE_SCALE = 400.0 / math.log(10.0)
SCORE_MEAN = 1500.0
COULD_BE_LEVEL = 0.9  # Could be holds this share of an item's rank draws


@dataclass(frozen=True)
class ItemStat:
    index: int  # position in the fit's theta vector
    rank: int  # 1 = best
    theta: float
    sd: float
    score: float  # Elo scale, 1500 = average of the ranked items
    confidence: float | None  # P(this item is really above the next one); None for the last
    rank_lo: int  # Could be: the narrowest run of ranks holding 90% of the draws...
    rank_hi: int  # ...stretched to include the rank shown
    reach_lo: int  # the wider range the stopping rules use: 5th to 95th percentile,
    reach_hi: int  # rounded outward and stretched to include the rank shown


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def summarize(
    theta: np.ndarray,
    cov: np.ndarray,
    indices: np.ndarray,
    *,
    seed: int,
    draws: int = 1000,
) -> list[ItemStat]:
    """Rank the items at ``indices`` and describe how sure the ranking is.

    ``theta`` and ``cov`` cover every item in the fit. Only ``indices`` are ranked, so
    removed items still inform the fit but don't take up a place. The Could be range
    is drawn from the normal approximation, with a fixed seed so it can be rebuilt.
    """
    idx = np.asarray(indices, dtype=np.int64)
    k = len(idx)
    if k == 0:
        return []
    mu = theta[idx]
    s = cov[np.ix_(idx, idx)]
    # Best first. Rounding first keeps float noise (warm vs cold start) from flipping the order
    # of exactly tied items; ties are then broken by index.
    order = np.lexsort((idx, -np.round(mu, 9)))
    scores = SCORE_MEAN + SCORE_SCALE * (mu - mu.mean())
    sds = np.sqrt(np.clip(np.diag(s), 0.0, None))

    rank_lo, rank_hi, reach_lo, reach_hi = _rank_ranges(mu, s, order, seed=seed, draws=draws)

    out = []
    for r, i in enumerate(order):
        conf = None
        if r + 1 < k:
            j = order[r + 1]
            var = s[i, i] + s[j, j] - 2.0 * s[i, j]
            diff = mu[i] - mu[j]
            conf = _normal_cdf(diff / math.sqrt(var)) if var > 0 else (1.0 if diff > 0 else 0.5)
        out.append(
            ItemStat(
                index=int(idx[i]),
                rank=r + 1,
                theta=float(mu[i]),
                sd=float(sds[i]),
                score=float(scores[i]),
                confidence=conf,
                rank_lo=int(rank_lo[i]),
                rank_hi=int(rank_hi[i]),
                reach_lo=int(reach_lo[i]),
                reach_hi=int(reach_hi[i]),
            )
        )
    return out


def could_be(ranks: np.ndarray, level: float = COULD_BE_LEVEL) -> tuple[np.ndarray, np.ndarray]:
    """For rank draws (draws, items), each item's narrowest run of ranks holding ``level`` of
    its draws; among equally narrow runs, the one holding most. A central range (5th to 95th
    percentile) was used first; ranks are whole numbers, so it rounded outward and held the
    true rank 95-100% of the time in the benchmark, against the 90% it claims. The narrowest
    run is about 10-20% shorter at the same level."""
    draws, k = ranks.shape
    counts = np.zeros((k, k))
    np.add.at(counts, (np.tile(np.arange(k), draws), ranks.ravel() - 1), 1.0)
    cum = np.concatenate([np.zeros((k, 1)), np.cumsum(counts, axis=1)], axis=1) / draws
    starts = np.arange(k)
    lo = np.empty(k, dtype=np.int64)
    hi = np.empty(k, dtype=np.int64)
    for x in range(k):
        c = cum[x]
        ends = np.searchsorted(c, c[:-1] + level - 1e-9)  # the run covers ranks a+1 .. end
        width = np.where(ends <= k, ends - starts, k + 1)
        narrowest = np.flatnonzero(width == width.min())
        held = c[np.minimum(ends[narrowest], k)] - c[narrowest]
        a = int(narrowest[np.argmax(held)])
        lo[x], hi[x] = a + 1, int(min(ends[a], k))
    return lo, hi


def reach(ranks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For rank draws (draws, items), the 5th to 95th percentile of each item's rank,
    rounded outward. The stopping rules ask whether an item below the part a mode settles
    could still reach into it, and use this wider range as a margin: with Could be's
    narrower one, Stable stopped sooner with the human judge and got fewer pairs right."""
    lo = np.quantile(ranks, 0.05, axis=0, method="lower").astype(np.int64)
    hi = np.quantile(ranks, 0.95, axis=0, method="higher").astype(np.int64)
    return lo, hi


def _rank_ranges(
    mu: np.ndarray, s: np.ndarray, order: np.ndarray, *, seed: int, draws: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(Could be low, high, reach low, high), each stretched to include the rank shown."""
    k = len(mu)
    if k == 1:
        one = np.ones(1, dtype=np.int64)
        return one, one, one, one
    rng = np.random.default_rng(seed)
    jitter = 1e-12 * max(1.0, float(np.mean(np.diag(s))))
    try:
        chol = np.linalg.cholesky(s + jitter * np.eye(k))
    except np.linalg.LinAlgError:
        w, v = np.linalg.eigh(s)
        chol = v * np.sqrt(np.clip(w, 0.0, None))
    samples = mu + rng.standard_normal((draws, k)) @ chol.T
    # Rank 1 = largest score in each draw.
    ranks = np.empty((draws, k), dtype=np.int64)
    ranks[np.arange(draws)[:, None], np.argsort(-samples, axis=1)] = np.arange(1, k + 1)
    lo, hi = could_be(ranks)
    far_lo, far_hi = reach(ranks)
    # The point-estimate rank is always a possible rank.
    point = np.empty(k, dtype=np.int64)
    point[order] = np.arange(1, k + 1)
    return (
        np.minimum(lo, point),
        np.maximum(hi, point),
        np.minimum(far_lo, point),
        np.maximum(far_hi, point),
    )
