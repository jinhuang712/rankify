"""What the screen shows: Score, Confidence and Could be, derived from a fit."""

import math
from dataclasses import dataclass

import numpy as np

# Elo points per natural-log unit: 400 / ln 10.
SCORE_SCALE = 400.0 / math.log(10.0)
SCORE_MEAN = 1500.0


@dataclass(frozen=True)
class ItemStat:
    index: int  # position in the fit's theta vector
    rank: int  # 1 = best
    theta: float
    sd: float
    score: float  # Elo scale, 1500 = average of the ranked items
    confidence: float | None  # P(this item is really above the next one); None for the last
    rank_lo: int  # Could be: 5th percentile of the rank
    rank_hi: int  # Could be: 95th percentile of the rank


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

    rank_lo, rank_hi = _rank_ranges(mu, s, order, seed=seed, draws=draws)

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
            )
        )
    return out


def _rank_ranges(
    mu: np.ndarray, s: np.ndarray, order: np.ndarray, *, seed: int, draws: int
) -> tuple[np.ndarray, np.ndarray]:
    k = len(mu)
    if k == 1:
        return np.ones(1, dtype=np.int64), np.ones(1, dtype=np.int64)
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
    lo = np.quantile(ranks, 0.05, axis=0, method="lower").astype(np.int64)
    hi = np.quantile(ranks, 0.95, axis=0, method="higher").astype(np.int64)
    # The point-estimate rank is always a possible rank.
    point = np.empty(k, dtype=np.int64)
    point[order] = np.arange(1, k + 1)
    return np.minimum(lo, point), np.maximum(hi, point)
