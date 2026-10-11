"""The answer model: Bradley–Terry pairs with Davidson ties, and Plackett–Luce pick and
rank rounds, all sharing one score per item and one first-slot bonus.

All parameters live in one vector ``x = [theta_0 .. theta_{n-1}, beta, lam]``:

- ``theta``: item scores on the natural-log scale.
- ``beta``: bonus for the item shown first (position bias).
- ``lam``: log of Davidson's tie parameter ``nu``.

For a pair with item ``a`` shown first and ``b`` second, the answer is a softmax over

    [u_a, u_b, lam + (u_a + u_b) / 2],   u_a = theta_a + beta,   u_b = theta_b

for "a wins", "b wins" and "can't decide". Without ties the last logit is dropped,
which is plain Bradley–Terry.

A pick round ("which is best?") is one softmax choice over the shown items (Luce 1959).
A rank round ("put these in order") is read as k - 1 choices: the best of all, then the
best of the rest, and so on (Plackett 1975). Every choice is a log-softmax of utilities
that are linear in ``x``, so the log posterior stays concave and has one best fit.
"""

from dataclasses import dataclass, field

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


K_MAX = 5  # the most items one round shows


@dataclass(frozen=True)
class Choices:
    """Every choice made in pick and rank rounds, one row per choice, padded to K_MAX."""

    sets: np.ndarray  # (m, K_MAX) item positions; the chosen item is in column 0; -1 = empty
    first: np.ndarray  # (m, K_MAX) True for the item that was shown first in its round
    cache: dict = field(default_factory=dict, compare=False, repr=False)  # see _layout

    @staticmethod
    def of(rounds) -> "Choices":
        """``rounds``: (shown in display order, answer). A pick round's answer is the one
        chosen item; a rank round's answer is every shown item, best first."""
        sets, first = [], []
        for shown, answer in rounds:
            shown, answer = list(shown), list(answer)
            if len(shown) > K_MAX or len(set(shown)) != len(shown) or not set(answer) <= set(shown):
                raise ValueError("a round shows 2 to 5 different items and answers among them")
            if len(answer) == 1:  # pick: the chosen one, then the rest in display order
                stages = [[answer[0]] + [x for x in shown if x != answer[0]]]
            elif len(answer) == len(shown):  # rank: best of all, best of the rest, ...
                stages = [answer[r:] for r in range(len(answer) - 1)]
            else:
                raise ValueError("an answer picks one item or orders them all")
            for row in stages:
                sets.append(row + [-1] * (K_MAX - len(row)))
                first.append([x == shown[0] for x in row] + [False] * (K_MAX - len(row)))
        if not sets:
            return Choices(np.zeros((0, K_MAX), np.int64), np.zeros((0, K_MAX), bool))
        return Choices(np.array(sets, np.int64), np.array(first, bool))

    def __len__(self) -> int:
        return len(self.sets)


NO_CHOICES = Choices.of([])


def _choice_probs(x: np.ndarray, n: int, c: Choices) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Softmax probabilities over each choice's items (0 where empty), and log-sum-exp."""
    valid = c.sets >= 0
    u = np.where(valid, x[:n][np.maximum(c.sets, 0)] + x[n] * c.first, -np.inf)
    top = u.max(axis=1, keepdims=True)
    e = np.where(valid, np.exp(u - top), 0.0)
    total = e.sum(axis=1, keepdims=True)
    return e / total, (top + np.log(total))[:, 0], u


def _choice_log_lik(x: np.ndarray, n: int, c: Choices) -> float:
    if len(c) == 0:
        return 0.0
    _, lse, u = _choice_probs(x, n, c)
    return float(np.sum(u[:, 0] - lse))


def _layout(c: Choices, size: int) -> tuple:
    """Index arrays for scattering the choices into a (size, size) Hessian. They depend
    only on the choices, so a fit computes them once, not on every Newton step."""
    key = ("layout", size)
    if key not in c.cache:
        valid = c.sets >= 0
        idx = np.where(valid, c.sets, 0)
        both = valid[:, :, None] & valid[:, None, :]
        shape = (len(c), K_MAX, K_MAX)
        rows = np.broadcast_to(idx[:, :, None], shape)[both]
        cols = np.broadcast_to(idx[:, None, :], shape)[both]
        c.cache[key] = (valid, idx, both, rows * size + cols)
    return c.cache[key]


def _choice_grad_hess(x: np.ndarray, n: int, c: Choices, g: np.ndarray, h: np.ndarray) -> None:
    """Add the choices' gradient and Hessian into ``g`` and ``h`` (in place).

    A choice's utilities are u = theta[set] + beta * first, and a log-softmax has Hessian
    -(diag(p) - p p^T) in u. With J = [I | first], the Hessian over (theta[set], beta) is
    -J^T C J: the theta block -C, the cross terms -C first, and -first^T C first for beta.
    """
    if len(c) == 0:
        return
    size = len(g)
    p, _, _ = _choice_probs(x, n, c)
    valid, idx, both, flat = _layout(c, size)
    f = c.first.astype(float)
    resid = -p
    resid[:, 0] += 1.0
    g += np.bincount(idx[valid], weights=resid[valid], minlength=size)
    g[n] += float(np.sum(resid * f))
    cmat = -(p[:, :, None] * p[:, None, :])
    diag = np.arange(K_MAX)
    cmat[:, diag, diag] += p
    h -= np.bincount(flat, weights=cmat[both], minlength=size * size).reshape(size, size)
    cf = np.einsum("mij,mj->mi", cmat, f)
    cross = np.bincount(idx[valid], weights=cf[valid], minlength=size)
    h[:n, n] -= cross[:n]
    h[n, :n] -= cross[:n]
    h[n, n] -= float(np.einsum("mi,mi->", f, cf))


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


def log_posterior(
    x: np.ndarray, n: int, pairs: Pairs, prior: Prior, ties: bool, choices: Choices = NO_CHOICES
) -> float:
    """Log likelihood of the answers plus the log prior (up to a constant)."""
    lp = _log_prior(x, n, prior) + _choice_log_lik(x, n, choices)
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
    x: np.ndarray, n: int, pairs: Pairs, prior: Prior, ties: bool, choices: Choices = NO_CHOICES
) -> tuple[np.ndarray, np.ndarray]:
    """Gradient and Hessian of ``log_posterior`` with respect to ``x``."""
    size = n + 2
    g = np.zeros(size)
    h = np.zeros((size, size))
    _choice_grad_hess(x, n, choices, g, h)
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
