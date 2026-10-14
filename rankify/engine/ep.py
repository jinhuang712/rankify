"""Expectation propagation (Minka 2001) for pair answers: a Gaussian over the item scores
that matches what each answer implies about the scores' mean and spread, not only their peak.

The Laplace fit in ``fit.py`` centres its Gaussian on the single most likely set of scores.
An answer "a beats b" holds for every larger gap too, so with a judge who seldom contradicts
themself most believable scores lie far beyond that peak. The Laplace Gaussian misses them:
it sits too close to the middle and is too narrow, and the prior width learned from it comes
out several times too small (Kuss & Rasmussen 2005 found the same for classification). EP
gives each answer a Gaussian factor along its gap and fits it so that the posterior's mean and
variance along that gap match what the answer really implies.

Each pair answer depends on one gap s = theta_a - theta_b, plus the first-slot bonus beta and
the tie weight lam that all answers share, as in ``model.py``. Every factor is updated at once
from the current posterior (parallel EP), so the result depends only on the set of answers,
never on their order. The bonus, the tie weight and the prior width are point estimates, each
set where the EP approximation of the evidence peaks: the width by expectation-maximization
(Dempster, Laird & Rubin 1977), the bonus and tie weight by Newton steps.
"""

import math

import numpy as np

from rankify.engine.fit import DEFAULT_SIGMA_PRIOR, Fit, FitError, SigmaPrior, _best_log_sigma
from rankify.engine.model import A_WINS, B_WINS, DEFAULT_PRIOR, TIE, Pairs, Prior

_GH_X, _GH_W = np.polynomial.hermite.hermgauss(24)
_GH_LOGW = np.log(_GH_W) + _GH_X**2  # quadrature at the peak: weights times e^(x^2)
_NARROW = 1.0  # cavity variances up to this use quadrature at the peak, wider ones the grid
_GRID_H = 0.5
_GRID = _GRID_H * np.arange(-120, 121)  # +-60 around the likelihood's midpoint
_SIGN = np.array([1.0, -1.0, 0.0])  # by answer: a wins, b wins, can't decide
_erf = np.vectorize(math.erf, otypes=[float])


def _phi_cdf(z):
    return 0.5 * (1.0 + _erf(z / math.sqrt(2.0)))


def _lik(d, y, lam: float, ties: bool):
    """Log likelihood of answer ``y`` at gap ``d`` (bonus included), its derivative and second
    derivative in ``d``, and in ``lam``. The logits are [d/2, -d/2, lam] (Davidson 1970)."""
    half = 0.5 * d
    if ties:
        top = np.maximum(np.abs(half), lam)
        ea, eb, et = np.exp(half - top), np.exp(-half - top), np.exp(lam - top)
        total = ea + eb + et
        lse = top + np.log(total)
        pa, pb, pt = ea / total, eb / total, et / total
    else:
        lse = np.logaddexp(half, -half)
        pa, pb = np.exp(half - lse), np.exp(-half - lse)
        pt = np.zeros_like(half)
    zy = np.where(y == A_WINS, half, np.where(y == B_WINS, -half, lam))
    ex = 0.5 * (pa - pb)  # E[d logit / d d] over the softmax
    g_d = np.where(y == A_WINS, 0.5, np.where(y == B_WINS, -0.5, 0.0)) - ex
    h_dd = -(0.25 * (pa + pb) - ex**2)
    g_l = (y == TIE) - pt
    h_ll = -pt * (1.0 - pt)
    return zy - lse, g_d, h_dd, g_l, h_ll


class _Grid:
    """Tables for wide cavities, which depend only on the tie weight. Each answer's likelihood
    is a smooth step (or, for "can't decide", a bump) around a midpoint. The step is split
    into a normal curve, whose product with the cavity has closed-form moments, and a smooth
    remainder that dies off within +-60 of the midpoint. The remainder is analytic in a strip
    of half-width pi around the real line, so the trapezoid rule on it is accurate to about
    exp(-2 pi^2 / h) (Trefethen & Weideman 2014)."""

    def __init__(self, lam: float, ties: bool):
        nu = math.exp(lam) if ties else 0.0
        self.mid = 2.0 * math.log((nu + math.sqrt(nu * nu + 4.0)) / 2.0)  # P(a wins) = 1/2
        _, g, *_ = _lik(np.array([self.mid]), np.array([A_WINS]), lam, ties)
        self.kappa = 0.5 * float(g[0]) * math.sqrt(2.0 * math.pi)  # the normal curve's slope
        rows = [], [], []
        for k, y in enumerate((A_WINS, B_WINS, TIE)):
            d = _SIGN[k] * self.mid + _GRID
            ll, _, _, g_l, h_ll = _lik(d, np.full_like(d, y), lam, ties)
            f = np.exp(ll)
            step = _phi_cdf(_SIGN[k] * self.kappa * _GRID) if _SIGN[k] else 0.0
            rows[0].append(f - step)
            rows[1].append(f * g_l)
            rows[2].append(f * (g_l**2 + h_ll))
        self.rest, self.f_gl, self.f_gl2 = (np.array(r) for r in rows)


def _at_peak(mc, vc, y, beta, lam, ties):
    """Moments for narrow cavities, by Gauss-Hermite quadrature centred on the product's peak
    (Liu & Pierce 1994). The product is log-concave, so its peak is unique, and since the log
    likelihood's slope is at most 1 in size, the peak lies within mc +- vc. The quadrature
    hardly depends on where exactly it is centred, so the peak is needed only roughly: 12
    safeguarded Newton steps leave it within vc / 4096 even where every step bisects."""
    lo, hi = mc - vc, mc + vc
    s = mc.copy()
    for _ in range(12):
        _, g, h, _, _ = _lik(s + beta, y, lam, ties)
        d1 = -(s - mc) / vc + g
        up = d1 > 0
        lo, hi = np.where(up, s, lo), np.where(up, hi, s)
        new = s - d1 / (-1.0 / vc + h)
        new = np.where((new <= lo) | (new >= hi), 0.5 * (lo + hi), new)
        done = np.all(np.abs(new - s) <= 1e-9 * np.sqrt(vc))
        s = new
        if done:
            break
    _, _, h, _, _ = _lik(s + beta, y, lam, ties)
    width = 1.0 / np.sqrt(1.0 / vc - h)
    nodes = s[:, None] + math.sqrt(2.0) * width[:, None] * _GH_X[None, :]
    ll, _, _, g_l, h_ll = _lik(nodes + beta, y[:, None], lam, ties)
    logt = _GH_LOGW[None, :] + ll - (nodes - mc[:, None]) ** 2 / (2.0 * vc[:, None])
    w = np.exp(logt - logt.max(axis=1, keepdims=True))
    w /= w.sum(axis=1, keepdims=True)
    mean = np.sum(w * nodes, axis=1)
    dev = nodes - mean[:, None]
    var = np.sum(w * dev**2, axis=1)
    e_gl = np.sum(w * g_l, axis=1)
    return mean, var, e_gl, np.sum(w * (g_l**2 + h_ll), axis=1), np.sum(w * dev * g_l, axis=1)


def _on_grid(mc, vc, y, beta, grid: _Grid):
    """Moments for wide cavities: the normal-curve part in closed form, the remainder on the
    grid. Returns NaN where the product's mass is too small to measure."""
    sign = _SIGN[y]
    centre = sign * grid.mid - beta  # the likelihood's midpoint, as a gap without the bonus
    # Normal-curve part, Phi(a X + b) with X = s - mc ~ Normal(0, vc).
    a = sign * grid.kappa
    b = a * (mc - centre)
    q = np.sqrt(1.0 + a * a * vc)
    z = b / q
    pdf = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = np.where(sign != 0, _phi_cdf(z), 0.0)
    pdf = np.where(sign != 0, pdf, 0.0)
    z0, z1, z2 = cdf, a * vc * pdf / q, vc * cdf - a * a * vc * vc * z * pdf / (q * q)
    # Remainder, trapezoid rule.
    x = (centre - mc)[:, None] + _GRID[None, :]
    wts = _GRID_H * np.exp(-0.5 * x * x / vc[:, None]) / np.sqrt(2.0 * math.pi * vc)[:, None]
    rest = grid.rest[y]
    z0 = z0 + np.sum(wts * rest, axis=1)
    z1 = z1 + np.sum(wts * rest * x, axis=1)
    z2 = z2 + np.sum(wts * rest * x * x, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ex = z1 / z0
        var = z2 / z0 - ex * ex
        e_gl = np.sum(wts * grid.f_gl[y], axis=1) / z0
        e_gl2 = np.sum(wts * grid.f_gl2[y], axis=1) / z0
        cross = np.sum(wts * grid.f_gl[y] * x, axis=1) / z0 - ex * e_gl
    bad = ~(z0 > 1e-280) | ~(var > 0)
    out = [mc + ex, var, e_gl, e_gl2, cross]
    return [np.where(bad, np.nan, o) for o in out]


def _moments(mc, vc, y, beta, lam, ties, grid: _Grid):
    """For each answer, the cavity Normal(mc, vc) over its gap times its likelihood: the
    product's mean and variance, and for the tie weight's Newton step E[g], E[g^2 + h] and
    Cov(gap, g), where g and h are the log likelihood's derivatives in lam."""
    out = [np.empty_like(mc) for _ in range(5)]
    narrow = vc <= _NARROW
    wide = ~narrow
    if np.any(wide):
        res = _on_grid(mc[wide], vc[wide], y[wide], beta, grid)
        failed = np.isnan(res[0])
        for o, r in zip(out, res, strict=True):
            o[wide] = r
        if np.any(failed):  # far outside the grid: the peak quadrature is fine there
            narrow = narrow.copy()
            narrow[np.flatnonzero(wide)[failed]] = True
    if np.any(narrow):
        res = _at_peak(mc[narrow], vc[narrow], y[narrow], beta, lam, ties)
        for o, r in zip(out, res, strict=True):
            o[narrow] = r
    return out


class _Posterior:
    """The prior Normal(0, sigma^2 I) over item scores times one Gaussian factor per answer
    along its gap, kept in natural parameters (precision tau, precision times mean nu)."""

    def __init__(self, n: int, pairs: Pairs, tau=None, nu=None):
        self.n, self.a, self.b = n, pairs.a, pairs.b
        m = len(pairs)
        self.tau = np.zeros(m) if tau is None else np.array(tau, dtype=float)
        self.nu = np.zeros(m) if nu is None else np.array(nu, dtype=float)
        a, b = self.a, self.b
        self._flat = np.concatenate([a * n + a, b * n + b, a * n + b, b * n + a])

    def solve(self, sigma: float):
        n, t = self.n, self.tau
        # (bincount gives integers when there are no answers, hence the casts)
        prec = (
            np.bincount(self._flat, weights=np.concatenate([t, t, -t, -t]), minlength=n * n)
            .reshape(n, n)
            .astype(float)
        )
        prec[np.arange(n), np.arange(n)] += 1.0 / sigma**2
        shift = (
            np.bincount(self.a, weights=self.nu, minlength=n)
            - np.bincount(self.b, weights=self.nu, minlength=n)
        ).astype(float)
        cov = np.linalg.inv(prec)
        cov = 0.5 * (cov + cov.T)
        mean = cov @ shift
        m_gap = mean[self.a] - mean[self.b]
        v_gap = cov[self.a, self.a] + cov[self.b, self.b] - 2.0 * cov[self.a, self.b]
        return mean, cov, m_gap, v_gap


def _ep(post: _Posterior, sigma, y, beta, lam, ties, tol, max_sweeps=5000):
    """Parallel EP from the posterior's current factors to the fixed point. Damped; the
    damping halves whenever a sweep moves the factors more than the sweep before."""
    grid = _Grid(lam, ties)
    damp, last = 0.7, math.inf
    for sweep in range(1, max_sweeps + 1):
        mean, cov, m_gap, v_gap = post.solve(sigma)
        tc = 1.0 / v_gap - post.tau  # cavity precision
        ok = tc > 1e-12
        nc = m_gap / v_gap - post.nu
        mc, vc = nc[ok] / tc[ok], 1.0 / tc[ok]
        mom = _moments(mc, vc, y[ok], beta, lam, ties, grid)
        new_tau = np.maximum(1.0 / mom[1] - tc[ok], 0.0)
        new_nu = mom[0] / mom[1] - nc[ok]
        move = np.abs(new_tau - post.tau[ok]) * v_gap[ok] + np.abs(new_nu - post.nu[ok]) * np.sqrt(
            v_gap[ok]
        )
        worst = float(np.max(move, initial=0.0))
        if worst < tol:
            return mean, cov, (ok, mc, vc, mom), sweep
        if worst > last:
            damp = max(0.02, 0.5 * damp)
        last = worst
        post.tau[ok] += damp * (new_tau - post.tau[ok])
        post.nu[ok] += damp * (new_nu - post.nu[ok])
    raise FitError(f"EP did not converge in {max_sweeps} sweeps")


def _shared_step(stats, beta, lam, prior: Prior, bias: bool, ties: bool):
    """One Newton step for the bonus and the tie weight on the EP evidence: each answer's log
    normalizer, with its cavity held fixed, plus the priors. The bonus shifts every gap, so
    its derivatives are the cavity-mean ones: (mean - mc) / vc and (var - vc) / vc^2."""
    _, mc, vc, (mean, var, e_gl, e_gl2, cross) = stats
    grad = np.array(
        [
            float(np.sum((mean - mc) / vc)) - beta / prior.bias_sd**2,
            float(np.sum(e_gl)) - (lam - prior.tie_mean) / prior.tie_sd**2,
        ]
    )
    hess = np.array(
        [
            [float(np.sum((var - vc) / vc**2)) - 1.0 / prior.bias_sd**2, float(np.sum(cross / vc))],
            [float(np.sum(cross / vc)), float(np.sum(e_gl2 - e_gl**2)) - 1.0 / prior.tie_sd**2],
        ]
    )
    idx = np.flatnonzero([bias, ties])
    step = np.zeros(2)
    if len(idx):
        step[idx] = np.linalg.solve(hess[np.ix_(idx, idx)], -grad[idx])
    return beta + step[0], lam + step[1], hess


def fit_pairs_ep(
    n: int,
    pairs: Pairs,
    prior: Prior = DEFAULT_PRIOR,
    hyper: SigmaPrior = DEFAULT_SIGMA_PRIOR,
    *,
    ties: bool = True,
    bias: bool = True,
    learn_sigma: bool = True,
    x0: np.ndarray | None = None,
    sigma0: float | None = None,
    sites: tuple[np.ndarray, np.ndarray] | None = None,
    tol: float = 1e-10,
    max_rounds: int = 500,
) -> Fit:
    """Fit item scores to pair answers by EP, learning the bonus, the tie weight and (with
    ``learn_sigma``) the prior width from the answers. ``x0``, ``sigma0`` and ``sites`` (the
    factors of an earlier fit, one per answer, in the same order) warm-start the fit; like
    the Laplace fit, the result depends only on the answers."""
    if len(pairs) and (pairs.a.max(initial=-1) >= n or pairs.b.max(initial=-1) >= n):
        raise ValueError("pair refers to an item index outside 0..n-1")
    if not ties and np.any(pairs.y == TIE):
        raise ValueError("tie answers need ties=True")
    y = pairs.y
    beta = float(x0[n]) if (x0 is not None and bias) else 0.0
    lam = float(x0[n + 1]) if (x0 is not None and ties) else prior.tie_mean
    s = math.log(sigma0 if sigma0 else (hyper.center if learn_sigma else prior.sigma))
    post = _Posterior(n, pairs, *(sites or (None, None)))
    sweeps, hess = 0, None
    seen_v, seen_f = [], []
    # Solve EP only as precisely as the shared values are already known (inexact EM): far
    # from the end a rough fixed point steers them as well as an exact one.
    inner = 1e-3
    for _ in range(max_rounds):
        mean, cov, stats, k = _ep(post, math.exp(s), y, beta, lam, ties, max(tol, inner))
        sweeps += k
        v = np.array([s, beta, lam])
        nb, nl = beta, lam
        if len(pairs) and (bias or ties):
            nb, nl, hess = _shared_step(stats, beta, lam, prior, bias, ties)
        em = _best_log_sigma(float(mean @ mean + np.trace(cov)), n, s, hyper) if learn_sigma else s
        f = np.array([em, nb, nl]) - v  # one EM step for the width, one Newton step for the rest
        worst = float(np.max(np.abs(f)))
        if worst < tol and inner <= tol:
            break
        inner = min(inner, 0.01 * worst)
        # Each value's step uses the others' old values, so plain steps converge only
        # linearly. Anderson acceleration (Walker & Ni 2011) mixes the last few steps; with
        # one value it is the secant method. Kept only when it moves the way the plain step
        # does and no more than one unit further.
        seen_v, seen_f = (seen_v + [v])[-4:], (seen_f + [f])[-4:]
        new = v + f
        if len(seen_v) >= 2:
            df = np.diff(np.array(seen_f, dtype=float), axis=0).T
            dg = df + np.diff(np.array(seen_v, dtype=float), axis=0).T
            gamma = np.linalg.lstsq(df, f, rcond=None)[0]
            mixed = v + f - dg @ gamma
            step = mixed - v
            if (
                np.all(np.isfinite(step))
                and step @ f > 0
                and np.all(np.abs(step) <= np.abs(f) + 1.0)
            ):
                new = mixed
        s, beta, lam = float(new[0]), float(new[1]), float(new[2])
    else:
        raise FitError(f"EP fit did not converge in {max_rounds} rounds")
    x = np.concatenate([mean, [beta if bias else 0.0, lam if ties else prior.tie_mean]])
    full = np.zeros((n + 2, n + 2))
    full[:n, :n] = cov
    if hess is not None:
        for i, on in ((n, bias), (n + 1, ties)):
            if on:
                full[i, i] = -1.0 / hess[i - n, i - n]
    return Fit(
        x=x,
        cov=full,
        n=n,
        iterations=sweeps,
        log_posterior=float("nan"),
        sigma=math.exp(s) if learn_sigma else None,
        state=(post.tau.copy(), post.nu.copy()),
    )
