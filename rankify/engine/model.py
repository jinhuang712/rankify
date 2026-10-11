"""Pair rounds: Bradley–Terry with Davidson ties and a first-slot bonus.

All parameters live in one vector ``x = [theta_0 .. theta_{n-1}, beta, lam]``:

- ``theta``: item scores on the natural-log scale.
- ``beta``: bonus for the item shown first (position bias).
- ``lam``: log of Davidson's tie parameter ``nu``.

For a pair with item ``a`` shown first and ``b`` second, the answer is a softmax over

    [u_a, u_b, lam + (u_a + u_b) / 2],   u_a = theta_a + beta,   u_b = theta_b

for "a wins", "b wins" and "can't decide". Without ties the last logit is dropped,
which is plain Bradley–Terry.
"""

from dataclasses import dataclass

import numpy as np

A_WINS, B_WINS, TIE = 0, 1, 2

# Rows: d(logit_k) / d(theta_a, theta_b, beta, lam).
_J_TIES = np.array(
    [
        [1.0, 0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.5, 0.5, 0.5, 1.0],
    ]
)
_J_PLAIN = _J_TIES[:2]


@dataclass(frozen=True)
class Prior:
    """Normal priors. ``sigma`` keeps scores near the middle until answers move them."""

    sigma: float = 1.5
    bias_sd: float = 0.5
    tie_mean: float = float(np.log(0.2))
    tie_sd: float = 1.0


DEFAULT_PRIOR = Prior()


@dataclass(frozen=True)
class Pairs:
    """Answered pair rounds, as parallel integer arrays."""

    a: np.ndarray  # index of the item shown first
    b: np.ndarray  # index of the item shown second
    y: np.ndarray  # A_WINS, B_WINS or TIE

    @staticmethod
    def of(a, b, y) -> "Pairs":
        a, b, y = (np.asarray(v, dtype=np.int64) for v in (a, b, y))
        if not (a.shape == b.shape == y.shape) or a.ndim != 1:
            raise ValueError("a, b and y must be 1-D arrays of the same length")
        if np.any(a == b):
            raise ValueError("a pair needs two different items")
        if np.any((y < 0) | (y > 2)):
            raise ValueError("y must be A_WINS, B_WINS or TIE")
        return Pairs(a, b, y)

    def __len__(self) -> int:
        return len(self.y)


def _logits(x: np.ndarray, n: int, pairs: Pairs, ties: bool) -> np.ndarray:
    theta, beta, lam = x[:n], x[n], x[n + 1]
    ua = theta[pairs.a] + beta
    ub = theta[pairs.b]
    cols = [ua, ub] + ([lam + 0.5 * (ua + ub)] if ties else [])
    return np.stack(cols, axis=1)


def _softmax(z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    zmax = z.max(axis=1, keepdims=True)
    e = np.exp(z - zmax)
    s = e.sum(axis=1, keepdims=True)
    return e / s, (zmax + np.log(s))[:, 0]


def log_posterior(x: np.ndarray, n: int, pairs: Pairs, prior: Prior, ties: bool) -> float:
    """Log likelihood of the answers plus the log prior (up to a constant)."""
    lp = _log_prior(x, n, prior)
    if len(pairs) == 0:
        return lp
    z = _logits(x, n, pairs, ties)
    _, lse = _softmax(z)
    return float(np.sum(z[np.arange(len(pairs)), pairs.y] - lse)) + lp


def _log_prior(x: np.ndarray, n: int, prior: Prior) -> float:
    theta, beta, lam = x[:n], x[n], x[n + 1]
    return float(
        -0.5 * np.sum(theta**2) / prior.sigma**2
        - 0.5 * beta**2 / prior.bias_sd**2
        - 0.5 * (lam - prior.tie_mean) ** 2 / prior.tie_sd**2
    )


def grad_hess(
    x: np.ndarray, n: int, pairs: Pairs, prior: Prior, ties: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Gradient and Hessian of ``log_posterior`` with respect to ``x``."""
    size = n + 2
    g = np.zeros(size)
    h = np.zeros((size, size))
    if len(pairs):
        jac = _J_TIES if ties else _J_PLAIN
        p, _ = _softmax(_logits(x, n, pairs, ties))
        onehot = np.zeros_like(p)
        onehot[np.arange(len(pairs)), pairs.y] = 1.0
        # Per answer, over the four parameters it touches: (theta_a, theta_b, beta, lam).
        g_loc = (onehot - p) @ jac  # (m, 4)
        v = p @ jac  # (m, 4)
        outer = np.einsum("ki,kj->kij", jac, jac).reshape(len(jac), 16)
        h_loc = -((p @ outer).reshape(-1, 4, 4) - v[:, :, None] * v[:, None, :])
        idx = np.stack(
            [pairs.a, pairs.b, np.full_like(pairs.a, n), np.full_like(pairs.a, n + 1)], 1
        )
        g += np.bincount(idx.ravel(), weights=g_loc.ravel(), minlength=size)
        flat = (idx[:, :, None] * size + idx[:, None, :]).ravel()
        h += np.bincount(flat, weights=h_loc.ravel(), minlength=size * size).reshape(size, size)
    # Prior terms.
    g[:n] -= x[:n] / prior.sigma**2
    g[n] -= x[n] / prior.bias_sd**2
    g[n + 1] -= (x[n + 1] - prior.tie_mean) / prior.tie_sd**2
    h[np.arange(n), np.arange(n)] -= 1.0 / prior.sigma**2
    h[n, n] -= 1.0 / prior.bias_sd**2
    h[n + 1, n + 1] -= 1.0 / prior.tie_sd**2
    return g, h
