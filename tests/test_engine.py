import choix
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rankify.engine.fit import fit_pairs, initial_x
from rankify.engine.model import A_WINS, B_WINS, TIE, Pairs, Prior, grad_hess, log_posterior
from rankify.engine.stats import SCORE_SCALE, summarize


def simulate_pairs(theta, m, rng, *, bias=0.0, nu=0.0):
    """Answers from a Davidson/Bradley-Terry judge with a first-slot bonus."""
    n = len(theta)
    a = rng.integers(0, n, m)
    b = (a + rng.integers(1, n, m)) % n
    ua, ub = theta[a] + bias, theta[b]
    logits = np.stack([ua, ub, np.log(nu) + 0.5 * (ua + ub) if nu > 0 else np.full(m, -np.inf)], 1)
    p = np.exp(logits - logits.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    y = (rng.random(m)[:, None] > np.cumsum(p, axis=1)[:, :2]).sum(axis=1)
    return Pairs.of(a, b, y)


def test_gradient_and_hessian_match_finite_differences():
    rng = np.random.default_rng(0)
    n = 6
    pairs = simulate_pairs(rng.normal(0, 1, n), 40, rng, bias=0.3, nu=0.4)
    prior = Prior()
    x = rng.normal(0, 0.5, n + 2)
    g, h = grad_hess(x, n, pairs, prior, ties=True)
    eps = 1e-6
    for i in range(n + 2):
        e = np.zeros(n + 2)
        e[i] = eps
        fd = log_posterior(x + e, n, pairs, prior, True) - log_posterior(
            x - e, n, pairs, prior, True
        )
        assert fd / (2 * eps) == pytest.approx(g[i], abs=1e-6)
        g_plus, _ = grad_hess(x + e, n, pairs, prior, ties=True)
        g_minus, _ = grad_hess(x - e, n, pairs, prior, ties=True)
        np.testing.assert_allclose((g_plus - g_minus) / (2 * eps), h[:, i], atol=1e-5)


def test_fit_matches_choix():
    """Sanity check 1: plain Bradley-Terry with the same prior gives choix's scores."""
    rng = np.random.default_rng(1)
    n = 12
    sigma = 1.5
    pairs = simulate_pairs(rng.normal(0, 1.5, n), 300, rng)
    fit = fit_pairs(n, pairs, Prior(sigma=sigma), ties=False, bias=False)
    winners = np.where(pairs.y == A_WINS, pairs.a, pairs.b)
    losers = np.where(pairs.y == A_WINS, pairs.b, pairs.a)
    data = list(zip(winners.tolist(), losers.tolist()))
    # choix minimizes alpha * sum(theta^2) - loglik, so alpha = 1 / (2 sigma^2).
    ref = choix.opt_pairwise(n, data, alpha=1 / (2 * sigma**2), tol=1e-12)
    np.testing.assert_allclose(fit.theta, ref, atol=1e-4)


pair_data = st.integers(2, 10).flatmap(
    lambda n: st.tuples(
        st.just(n),
        st.lists(
            st.tuples(st.integers(0, n - 1), st.integers(1, n - 1), st.sampled_from([0, 1, 2])),
            max_size=60,
        ),
    )
)


@settings(max_examples=60, deadline=None)
@given(pair_data, st.randoms(use_true_random=False))
def test_order_of_answers_does_not_matter(data, rnd):
    """Sanity check 2: shuffling the answers leaves every number unchanged."""
    n, rows = data
    a = [r[0] for r in rows]
    b = [(r[0] + r[1]) % n for r in rows]
    y = [r[2] for r in rows]
    fit = fit_pairs(n, Pairs.of(a, b, y))
    perm = list(range(len(rows)))
    rnd.shuffle(perm)
    shuffled = fit_pairs(
        n, Pairs.of([a[i] for i in perm], [b[i] for i in perm], [y[i] for i in perm])
    )
    np.testing.assert_allclose(shuffled.x, fit.x, rtol=0, atol=1e-9)
    np.testing.assert_allclose(shuffled.cov, fit.cov, rtol=0, atol=1e-9)


def test_warm_start_reaches_the_same_fit():
    rng = np.random.default_rng(2)
    n = 20
    pairs = simulate_pairs(rng.normal(0, 1.5, n), 200, rng, bias=0.2, nu=0.3)
    cold = fit_pairs(n, pairs)
    warm = fit_pairs(n, pairs, x0=cold.x + rng.normal(0, 0.3, n + 2))
    np.testing.assert_allclose(warm.x, cold.x, atol=1e-9)


def test_recovers_scores_position_bias_and_ties():
    rng = np.random.default_rng(3)
    n = 10
    theta = np.linspace(-2, 2, n)
    pairs = simulate_pairs(theta, 20000, rng, bias=0.4, nu=0.5)
    fit = fit_pairs(n, pairs, Prior(sigma=5.0))
    assert fit.bias == pytest.approx(0.4, abs=0.05)
    assert fit.tie == pytest.approx(0.5, abs=0.05)
    np.testing.assert_allclose(fit.theta - fit.theta.mean(), theta - theta.mean(), atol=0.1)


def test_no_answers_gives_the_prior():
    n = 5
    fit = fit_pairs(n, Pairs.of([], [], []))
    np.testing.assert_allclose(fit.x, initial_x(n, Prior()))
    np.testing.assert_allclose(np.diag(fit.theta_cov), Prior().sigma ** 2)


def test_summary_ranks_scores_and_confidence():
    theta = np.array([0.0, 2.0, 1.0])
    cov = np.diag([0.01, 0.01, 0.01])
    stats = summarize(theta, cov, np.array([0, 1, 2]), seed=7)
    assert [s.index for s in stats] == [1, 2, 0]
    assert stats[0].score - stats[1].score == pytest.approx(SCORE_SCALE)
    assert stats[0].confidence > 0.99
    assert stats[-1].confidence is None
    assert [(s.rank_lo, s.rank_hi) for s in stats] == [(1, 1), (2, 2), (3, 3)]


def test_summary_could_be_widens_when_unsure():
    theta = np.array([0.0, 0.05, 0.1])
    cov = np.eye(3)
    stats = summarize(theta, cov, np.array([0, 1, 2]), seed=7)
    assert all(s.rank_lo == 1 and s.rank_hi == 3 for s in stats)
    assert all(0.5 < s.confidence < 0.6 for s in stats[:-1])


def test_summary_is_reproducible_with_the_same_seed():
    rng = np.random.default_rng(4)
    theta = rng.normal(0, 1, 30)
    cov = np.diag(rng.uniform(0.1, 0.5, 30))
    one = summarize(theta, cov, np.arange(30), seed=11)
    two = summarize(theta, cov, np.arange(30), seed=11)
    assert one == two


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        Pairs.of([0], [0], [A_WINS])
    with pytest.raises(ValueError):
        fit_pairs(3, Pairs.of([0], [1], [TIE]), ties=False)
    with pytest.raises(ValueError):
        fit_pairs(2, Pairs.of([0], [5], [B_WINS]))
