"""Best fit (maximum a posteriori) over all answers at once, by Newton's method.

The log posterior is concave in ``x``, so there is one best fit, and it depends only
on the set of answers, never on their order. The uncertainty comes from the Laplace
approximation: the covariance is the inverse of the negative Hessian at the best fit.
"""

from dataclasses import dataclass

import numpy as np

from rankify.engine.model import DEFAULT_PRIOR, Pairs, Prior, grad_hess, log_posterior


@dataclass(frozen=True)
class Fit:
    x: np.ndarray  # [theta_0 .. theta_{n-1}, beta, lam]
    cov: np.ndarray  # covariance of x; zero rows and columns for fixed parameters
    n: int
    iterations: int
    log_posterior: float

    @property
    def theta(self) -> np.ndarray:
        return self.x[: self.n]

    @property
    def theta_cov(self) -> np.ndarray:
        return self.cov[: self.n, : self.n]

    @property
    def bias(self) -> float:
        return float(self.x[self.n])

    @property
    def tie(self) -> float:
        """Davidson's ``nu``: the tie weight for two equal items."""
        return float(np.exp(self.x[self.n + 1]))


class FitError(RuntimeError):
    pass


def initial_x(n: int, prior: Prior) -> np.ndarray:
    x = np.zeros(n + 2)
    x[n + 1] = prior.tie_mean
    return x


def fit_pairs(
    n: int,
    pairs: Pairs,
    prior: Prior = DEFAULT_PRIOR,
    *,
    ties: bool = True,
    bias: bool = True,
    x0: np.ndarray | None = None,
    tol: float = 1e-10,
    max_iter: int = 100,
) -> Fit:
    """Fit item scores to pair answers.

    ``x0`` warm-starts the fit (for example from the previous fit). It changes how many
    steps the fit takes, not where it ends. ``ties=False`` gives plain Bradley–Terry, and
    ``bias=False`` fixes the first-slot bonus at zero.
    """
    if len(pairs) and (pairs.a.max(initial=-1) >= n or pairs.b.max(initial=-1) >= n):
        raise ValueError("pair refers to an item index outside 0..n-1")
    if not ties and np.any(pairs.y == 2):
        raise ValueError("tie answers need ties=True")

    x = initial_x(n, prior) if x0 is None else np.array(x0, dtype=float)
    if x.shape != (n + 2,):
        raise ValueError(f"x0 must have shape ({n + 2},)")
    free = np.ones(n + 2, dtype=bool)
    if not bias:
        free[n] = False
        x[n] = 0.0
    if not ties:
        free[n + 1] = False  # the tie parameter has no effect without ties
        x[n + 1] = prior.tie_mean

    f = log_posterior(x, n, pairs, prior, ties)
    neg_h = None
    for iteration in range(1, max_iter + 1):
        g, h = grad_hess(x, n, pairs, prior, ties)
        neg_h = -h[np.ix_(free, free)]
        step = np.linalg.solve(neg_h, g[free])
        # Backtrack only if a full Newton step would go downhill (far from the optimum).
        t = 1.0
        while True:
            x_new = x.copy()
            x_new[free] += t * step
            f_new = log_posterior(x_new, n, pairs, prior, ties)
            if f_new >= f - 1e-12 * max(1.0, abs(f)) or t < 1e-8:
                break
            t *= 0.5
        x, f = x_new, f_new
        if np.max(np.abs(t * step), initial=0.0) < tol:
            break
    else:
        raise FitError(f"fit did not converge in {max_iter} Newton steps")

    cov = np.zeros((n + 2, n + 2))
    cov[np.ix_(free, free)] = np.linalg.inv(neg_h)
    return Fit(x=x, cov=cov, n=n, iterations=iteration, log_posterior=f)
