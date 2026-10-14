"""Best fit (maximum a posteriori) over all answers at once, by Newton's method.

The log posterior is concave in ``x``, so there is one best fit, and it depends only
on the set of answers, never on their order. The uncertainty comes from the Laplace
approximation: the covariance is the inverse of the negative Hessian at the best fit.
"""

import math
from dataclasses import dataclass, replace

import numpy as np

from rankify.engine.model import (
    DEFAULT_PRIOR,
    NO_CHOICES,
    Choices,
    Pairs,
    Prior,
    grad_hess,
    log_posterior,
)


@dataclass(frozen=True)
class Fit:
    x: np.ndarray  # [theta_0 .. theta_{n-1}, beta, lam]
    cov: np.ndarray  # covariance of x; zero rows and columns for fixed parameters
    n: int
    iterations: int
    log_posterior: float
    sigma: float | None = None  # the prior width the fit used, when it was learned
    state: tuple | None = None  # an EP fit's per-answer factors, to warm-start the next fit

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
    choices: Choices = NO_CHOICES,
) -> Fit:
    """Fit item scores to pair answers, and to pick and rank rounds given as ``choices``.

    ``x0`` warm-starts the fit (for example from the previous fit). It changes how many
    steps the fit takes, not where it ends. ``ties=False`` gives plain Bradley–Terry, and
    ``bias=False`` fixes the first-slot bonus at zero.
    """
    if len(choices) and choices.sets.max() >= n:
        raise ValueError("choice refers to an item index outside 0..n-1")
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

    f = log_posterior(x, n, pairs, prior, ties, choices)
    neg_h = None
    for iteration in range(1, max_iter + 1):
        g, h = grad_hess(x, n, pairs, prior, ties, choices)
        neg_h = -h[np.ix_(free, free)]
        step = np.linalg.solve(neg_h, g[free])
        # Backtrack only if a full Newton step would go downhill (far from the optimum).
        t = 1.0
        while True:
            x_new = x.copy()
            x_new[free] += t * step
            f_new = log_posterior(x_new, n, pairs, prior, ties, choices)
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


# ---------------------------------------------------------------- learning the prior width


@dataclass(frozen=True)
class SigmaPrior:
    """Belief about the prior width before any answers: log(sigma) ~ Normal(log(center), sd²).

    It keeps the learned width sensible on lists with few answers, where the data alone
    would let it collapse toward zero.
    """

    center: float = 1.5
    sd: float = 0.75


DEFAULT_SIGMA_PRIOR = SigmaPrior()


def fit_pairs_learning_sigma(
    n: int,
    pairs: Pairs,
    prior: Prior = DEFAULT_PRIOR,
    hyper: SigmaPrior = DEFAULT_SIGMA_PRIOR,
    *,
    ties: bool = True,
    bias: bool = True,
    x0: np.ndarray | None = None,
    sigma0: float | None = None,
    tol: float = 1e-10,
    max_rounds: int = 200,
    choices: Choices = NO_CHOICES,
) -> Fit:
    """Fit item scores and learn the prior width from the answers themselves.

    A consistent judge spreads items far apart, so the width grows and each answer counts
    for more. A judge who often contradicts themself keeps it narrow. The width maximizes the
    evidence (type-II maximum a posteriori; MacKay 1992), found by expectation-maximization
    over the Laplace posterior (Dempster, Laird & Rubin 1977), sped up by secant steps. The
    result depends only on the answers: ``x0`` and ``sigma0`` change the speed, not the end.
    """

    def update(log_sigma: float, x) -> tuple[float, Fit]:
        fit = fit_pairs(
            n,
            pairs,
            replace(prior, sigma=math.exp(log_sigma)),
            ties=ties,
            bias=bias,
            x0=x,
            choices=choices,
        )
        spread = float(np.sum(fit.theta**2) + np.trace(fit.theta_cov))
        return _best_log_sigma(spread, n, log_sigma, hyper), fit

    s = math.log(sigma0 if sigma0 else hyper.center)
    x, steps = x0, 0
    s_prev = g_prev = None
    for _ in range(max_rounds):
        em, fit = update(s, x)  # one EM step from s
        x, steps = fit.x, steps + 1
        g = em - s  # the EM residual; the width we want has g = 0
        if abs(g) < tol:
            s = em
            break
        # Plain EM can crawl (with few answers each step is ~0.95 of the last), so take a
        # secant step on the residual instead, but only when it moves the same way as the EM
        # step: far from the answer the residual can grow, and the secant would then run the
        # wrong way (Aitken's acceleration has the same flaw).
        step = em - s
        if s_prev is not None and g_prev is not None and abs(g - g_prev) > 1e-15:
            secant = -g * (s - s_prev) / (g - g_prev)
            if secant * g > 0:
                step = float(np.clip(secant, g - 1.0, g + 1.0))
        s_prev, g_prev, s = s, g, s + step
    else:
        raise FitError(f"prior width did not converge in {max_rounds} rounds")
    final = fit_pairs(
        n, pairs, replace(prior, sigma=math.exp(s)), ties=ties, bias=bias, x0=x, choices=choices
    )
    return replace(final, iterations=steps, sigma=math.exp(s))


def _best_log_sigma(spread: float, n: int, start: float, hyper: SigmaPrior) -> float:
    """M-step: the log width that best explains the scores' expected spread, given the
    hyperprior. Solves -n + spread * e^(-2s) - (s - mu) / tau² = 0 by Newton's method."""
    mu, tau2 = math.log(hyper.center), hyper.sd**2
    s = start
    for _ in range(100):
        e = spread * math.exp(-2 * s)
        g = -n + e - (s - mu) / tau2
        step = g / (2 * e + 1 / tau2)
        s += step
        if abs(step) < 1e-13:
            break
    return s
