import math

import choix
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rankify import service
from rankify.engine.ep import _Grid, _lik, _moments, fit_pairs_ep
from rankify.engine.fit import SigmaPrior, fit_pairs_learning_sigma
from rankify.engine.model import A_WINS, B_WINS, TIE, Pairs, Prior

from .conftest import SimulatedJudge, run_rounds
from .test_engine import simulate_pairs


def _brute(mc, vc, y, beta, lam, ties):
    """Mean and variance of Normal(mc, vc) times the answer's likelihood, on a fine grid."""
    sd = math.sqrt(vc)
    s = np.linspace(min(mc - 14 * sd, -80 - beta), max(mc + 14 * sd, 80 - beta), 400_001)
    logd = -((s - mc) ** 2) / (2 * vc) + _lik(s + beta, np.full_like(s, y), lam, ties)[0]
    w = np.exp(logd - logd.max())
    w /= w.sum()
    mean = float(np.sum(w * s))
    return mean, float(np.sum(w * (s - mean) ** 2))


@pytest.mark.parametrize("ties", [False, True])
@pytest.mark.parametrize("mc,vc", [(0.5, 0.3), (2.0, 4.0), (-20.0, 400.0), (0.0, 2000.0)])
def test_answer_moments_match_brute_force(ties, mc, vc):
    """Narrow cavities go through quadrature at the peak, wide ones through the grid; both
    must match direct integration, including a surprising answer far from the cavity."""
    lam = math.log(0.3)
    grid = _Grid(lam, ties)
    for y in (A_WINS, B_WINS, TIE) if ties else (A_WINS, B_WINS):
        got = _moments(np.array([mc]), np.array([vc]), np.array([y]), 0.4, lam, ties, grid)
        mean, var = _brute(mc, vc, y, 0.4, lam, ties)
        assert got[0][0] == pytest.approx(mean, abs=1e-5 * math.sqrt(var))
        assert got[1][0] == pytest.approx(var, rel=1e-5)


@pytest.mark.parametrize("sigma", [1.5, 10.0])
def test_ep_matches_choix(sigma):
    """Plain pairs with a fixed prior width give choix's EP posterior. choix approximates the
    logistic curve by five normal curves (from GPML), good to about 0.1%; ours integrates it."""
    rng = np.random.default_rng(3)
    n = 12
    pairs = simulate_pairs(rng.normal(0, sigma, n), 80, rng)
    fit = fit_pairs_ep(n, pairs, Prior(sigma=sigma), ties=False, bias=False, learn_sigma=False)
    winners = np.where(pairs.y == A_WINS, pairs.a, pairs.b)
    losers = np.where(pairs.y == A_WINS, pairs.b, pairs.a)
    data = list(zip(winners.tolist(), losers.tolist(), strict=True))
    mean, cov = choix.ep_pairwise(n, data, 1 / sigma**2, model="logit", max_iter=1000)
    scale = float(np.max(np.abs(mean)))
    np.testing.assert_allclose(fit.theta, mean, atol=3e-3 * scale)
    np.testing.assert_allclose(fit.theta_cov, cov, atol=3e-3 * float(np.max(cov)))


@settings(max_examples=15, deadline=None)
@given(st.integers(0, 10_000), st.randoms(use_true_random=False))
def test_ep_does_not_depend_on_answer_order_or_start(seed, rnd):
    rng = np.random.default_rng(seed)
    n, m = 8, 40
    a = rng.integers(0, n, m)
    b = (a + rng.integers(1, n, m)) % n
    y = rng.integers(0, 3, m)
    fit = fit_pairs_ep(n, Pairs.of(a, b, y))
    perm = list(range(m))
    rnd.shuffle(perm)
    tau, nu = fit.state
    shuffled = fit_pairs_ep(
        n,
        Pairs.of(a[perm], b[perm], y[perm]),
        x0=fit.x + 0.3,
        sigma0=fit.sigma * 2,
        sites=(tau[perm] * 1.5, nu[perm] * 0.5),
    )
    np.testing.assert_allclose(shuffled.x, fit.x, atol=1e-8)
    np.testing.assert_allclose(shuffled.cov, fit.cov, atol=1e-8)
    assert shuffled.sigma == pytest.approx(fit.sigma, abs=1e-8)


def test_ep_learns_the_spread_laplace_misses():
    """A fairly consistent judge (scores spread 3, so most pairs are clear): Laplace learns a
    width well below the truth, EP one close to it, with a flat starting belief so the
    answers alone decide. One list's width is noisy, so the test takes the median of eight."""
    flat = SigmaPrior(1.5, 10.0)
    ep, laplace = [], []
    for seed in range(8):
        rng = np.random.default_rng(1000 + seed)
        theta = rng.normal(0, 3.0, 20)
        pairs = simulate_pairs(theta, 150, rng)
        truth = float(np.sqrt(np.mean(theta**2)))
        ep.append(fit_pairs_ep(20, pairs, hyper=flat, ties=False, bias=False).sigma / truth)
        lap = fit_pairs_learning_sigma(20, pairs, hyper=flat, ties=False, bias=False)
        laplace.append(lap.sigma / truth)
    assert np.median(laplace) < 0.75
    assert 0.85 < np.median(ep) < 1.15


def test_ep_with_no_answers_is_the_starting_belief():
    fit = fit_pairs_ep(5, Pairs.of([], [], []))
    assert fit.sigma == pytest.approx(1.5)
    np.testing.assert_allclose(fit.theta, 0.0, atol=1e-12)
    np.testing.assert_allclose(fit.theta_cov, 1.5**2 * np.eye(5), atol=1e-12)


def test_ep_session_verifies(rk, monkeypatch):
    """With EP on, a session's warm-started fits match a cold refit from the log."""
    monkeypatch.setattr(service, "EP_FIT", True)
    rng = np.random.default_rng(5)
    names = [f"item-{k:02d}" for k in range(10)]
    truth = dict(zip(names, rng.normal(0, 3.0, len(names)), strict=True))
    rk.create_list("sim", "Simulated", names, seed=7)
    run_rounds(rk, "sim", SimulatedJudge(truth, seed=6), 40, mode="quick")
    assert rk._current(rk._list("sim")).params["fit"] == "ep"
    assert rk.verify("sim") == []
