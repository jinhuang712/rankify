"""Rounds left: the simulated rest of the session."""

import json
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from typer.testing import CliRunner

from rankify import store
from rankify.cli.main import app
from rankify.engine.fit import DEFAULT_SIGMA_PRIOR, fit_pairs, fit_pairs_learning_sigma
from rankify.engine.forecast import (
    Habits,
    _answer_pair,
    _Belief,
    _choice_step,
    _rewidth,
    _tie_step,
    _update,
    _width_sd,
    forecast_rounds,
    forecast_steps,
)
from rankify.engine.model import A_WINS, Choices, Pairs, Prior
from rankify.engine.planner import ALL_KINDS
from rankify.service import _sharpness, _sittings

from .conftest import SimulatedJudge, run_rounds

FIXED = {"budget_ms": 1e9, "max_sims": 16}  # the same number of simulations on any machine


def test_one_answer_moves_the_belief_to_the_exact_posterior_mean():
    """For a probit answer the closed-form step is exact: the gap d = theta_0 - theta_1 has
    prior variance v, and after "0 beat 1" its mean is v / sqrt(c^2 + v) * sqrt(2 / pi).
    It also lands near a full (logistic, posterior-mode) refit of the same answer."""
    prior = Prior(sigma=1.5)
    m, s = np.zeros(3), np.eye(3) * prior.sigma**2
    _update(m, s, 0, 1, i_won=True)
    v, c = 2 * prior.sigma**2, 1.702
    assert m[0] - m[1] == pytest.approx(v / math.sqrt(c**2 + v) * math.sqrt(2 / math.pi))
    assert m[2] == 0 and s[2, 2] == prior.sigma**2  # an item not shown is untouched
    fit = fit_pairs(3, Pairs.of([0], [1], [A_WINS]), prior, ties=False, bias=False)
    np.testing.assert_allclose(m, fit.theta, atol=0.15)
    np.testing.assert_allclose(np.diag(s), np.diag(fit.theta_cov), atol=0.15)


@pytest.mark.parametrize(
    ("sigma", "shown", "answer"),
    [
        (1.5, [0, 1, 2, 3], [2, 0, 3, 1]),  # put these in order
        (2.5, [0, 1, 2, 3, 4], [4]),  # a pick, under wide uncertainty
    ],
)
def test_a_set_answer_moves_the_belief_to_the_full_refit(sigma, shown, answer):
    """From the prior, the update is the same posterior mode and Laplace covariance as a
    full refit of the same answer under Plackett–Luce, even when the answer surprises."""
    prior = Prior(sigma=sigma)
    m, s = np.zeros(6), np.eye(6) * sigma**2
    _choice_step(m, s, np.array(shown), np.array(answer))
    fit = fit_pairs(6, Pairs.of([], [], []), prior, ties=False, bias=False,
                    choices=Choices.of([(shown, answer)]))  # fmt: skip
    np.testing.assert_allclose(m, fit.theta, atol=1e-6)
    np.testing.assert_allclose(s, fit.theta_cov, atol=1e-6)
    assert m[5] == 0


def test_cant_decide_pulls_two_items_together_without_flipping_them():
    """The mode of a "can't decide" under wide uncertainty, checked on a fine grid. A single
    Newton step from the mean used to overshoot here and swap the two items."""
    nu, v = 0.2, 12.0
    m, s = np.array([1.5, -1.5, 0.0]), np.eye(3) * v
    _tie_step(m, s, 0, 1, nu)
    grid = np.linspace(-6, 6, 1201)
    ua, ub = np.meshgrid(grid, grid, indexing="ij")
    tie = np.log(nu) + (ua + ub) / 2
    log_post = tie - np.logaddexp(np.logaddexp(ua, ub), tie)
    log_post -= ((ua - 1.5) ** 2 + (ub + 1.5) ** 2) / (2 * v)
    a, b = np.unravel_index(np.argmax(log_post), log_post.shape)
    assert m[0] - m[1] == pytest.approx(grid[a] - grid[b], abs=0.03)
    assert 0 < m[0] - m[1] < 3.0 and s[0, 0] < v and m[2] == 0.0


def test_cant_decide_comes_at_davidsons_rate():
    rng = np.random.default_rng(1)
    truth, nu = np.zeros(2), 0.5
    said = [_answer_pair(truth, 0, 1, Habits(tie=nu), 1.0, rng) for _ in range(20000)]
    assert np.mean(np.array(said) == 0) == pytest.approx(nu / (2 + nu), abs=0.01)


def test_the_width_is_as_unsure_as_its_hyperprior_before_any_answers():
    assert _width_sd(np.eye(6) * 1.5**2, 1.5) == pytest.approx(DEFAULT_SIGMA_PRIOR.sd)
    assert _width_sd(np.eye(6) * 0.1, 1.5) < 0.35  # every item pinned down


def test_orderings_finish_in_fewer_rounds_than_pairs():
    theta, cov = np.zeros(10), np.eye(10) * 2.25
    pairs = forecast_rounds("stable", theta, cov, list(range(10)), {}, 3, **FIXED)
    mixed = forecast_rounds("stable", theta, cov, list(range(10)), {}, 3, kinds=ALL_KINDS,
                            **FIXED)  # fmt: skip
    assert mixed.median < pairs.median


def test_a_tired_judge_needs_more_rounds():
    """Tiredness only: the same list, a fresh judge against one already 30 calls into a
    sitting whose noise grows 2% per call, over several seeds."""
    theta, cov = np.linspace(2, -2, 8), np.eye(8) * 2.25
    looks = dict.fromkeys(range(8), 2)
    fresh = Habits(fatigue=0.0)
    tired = Habits(fatigue=0.02)

    def rounds(habits, effort):
        kw = {"habits": habits, "effort": effort, "past_efforts": [], **FIXED}
        return sum(
            forecast_rounds("exact", theta, cov, list(range(8)), looks, seed, **kw).median
            for seed in range(4)
        )

    assert rounds(tired, 30) > 1.1 * rounds(fresh, 0)


def test_the_simulated_fit_learns_its_width_as_the_real_one_does():
    """Re-learning the width from a fit that has already learned it changes nothing, and
    redoing a fit for the same width gives it back."""
    rng = np.random.default_rng(3)
    truth = rng.normal(0, 2.0, 12)
    a, b, y = [], [], []
    for _ in range(80):
        i, j = rng.choice(12, 2, replace=False)
        a.append(i)
        b.append(j)
        y.append(A_WINS if rng.random() < 1 / (1 + np.exp(truth[j] - truth[i])) else 1)
    fit = fit_pairs_learning_sigma(12, Pairs.of(a, b, y), Prior(sigma=1.5), ties=False, bias=False)
    m, s = fit.theta.copy(), fit.theta_cov.copy()
    _rewidth(m, s, fit.sigma, fit.sigma)
    np.testing.assert_allclose(m, fit.theta, atol=1e-12)
    belief = _Belief(m, s, rng, fit.sigma)
    belief.relearn(steps=10)
    assert belief.sigma == pytest.approx(fit.sigma, rel=1e-6)
    for start in (0.5, 4.0):  # from another width, it finds its way back
        m2, s2 = fit.theta.copy(), fit.theta_cov.copy()
        _rewidth(m2, s2, fit.sigma, start)
        assert abs(m2 - fit.theta).max() > 0.1
        belief = _Belief(m2, s2, rng, start)
        belief.relearn(steps=200)
        assert belief.sigma == pytest.approx(fit.sigma, rel=0.05)
        np.testing.assert_allclose(m2, fit.theta, atol=0.05)


def test_sharpness_is_about_1_for_a_judge_the_model_describes_and_more_for_a_perfect_one():
    rng = np.random.default_rng(5)
    model, perfect = [], []
    for _ in range(300):
        mu, sd = rng.normal(0, 1.5), 0.3
        truth = rng.normal(mu, np.sqrt(2) * sd)  # the gap, drawn from what rankify expected
        before = {1: (mu, sd), 2: (0.0, sd)}
        won = 1 if rng.random() < 1 / (1 + np.exp(-truth)) else 2
        model.append(("pair", [1, 2], [won], before))
        perfect.append(("pair", [1, 2], [1 if truth > 0 else 2], before))
    assert _sharpness([]) == 1.0
    assert 0.8 < _sharpness(model) < 1.25
    assert _sharpness(perfect) > 2.0
    rankings = []  # orderings of 4 from a judge who follows the model exactly
    for _ in range(600):
        scores = rng.normal(0, 1.5, 4)
        order = np.argsort(-(scores + rng.gumbel(size=4)))
        before = {i: (float(scores[i]), 0.0) for i in range(4)}
        rankings.append(("rank", [0, 1, 2, 3], [int(i) for i in order], before))
    assert 0.85 < _sharpness(rankings) < 1.15


def test_fatigue_resets_between_sittings():
    def row(minute, judge=1, shown=(1, 2)):
        at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=minute)
        return store.RoundRow(0, judge, None, "pair", list(shown), None, "answered", None, 1000,
                              at.isoformat())  # fmt: skip

    rounds = [row(0), row(1), row(2, shown=(1, 2, 3, 4)), row(90), row(91, judge=2)]
    out = _sittings(rounds, 1, at=datetime(2026, 1, 1, 1, 32, tzinfo=UTC))
    assert out["past_efforts"] == [0, 1, 2, 3, 4, 0, 0]  # a ranking of 4 is 3 calls
    assert out["effort"] == 1  # judge 1's second sitting, under way
    later = _sittings(rounds, 1, at=datetime(2026, 1, 1, 3, 0, tzinfo=UTC))
    assert later["effort"] == 0  # a new sitting


def test_a_settled_list_has_no_rounds_left():
    theta = np.array([6.0, 4.0, 2.0, 0.0])
    cov = np.eye(4) * 1e-4
    f = forecast_rounds("exact", theta, cov, [0, 1, 2, 3], dict.fromkeys(range(4), 5), 1, **FIXED)
    assert (f.median, f.low, f.high) == (0, 0, 0)


def test_the_forecast_is_repeatable_and_shrinks_as_answers_come_in():
    theta, cov = np.zeros(8), np.eye(8) * 2.25
    early = forecast_rounds("stable", theta, cov, list(range(8)), {}, 7, **FIXED)
    again = forecast_rounds("stable", theta, cov, list(range(8)), {}, 7, **FIXED)
    assert (early.median, early.low, early.high) == (again.median, again.low, again.high)
    assert early.low <= early.median <= early.high
    spread = np.linspace(3, -3, 8)
    later = forecast_rounds(
        "stable", spread, np.eye(8) * 0.3, list(range(8)), dict.fromkeys(range(8), 4), 7, **FIXED
    )
    assert later.median < early.median


def test_the_forecast_pauses_between_simulations_too():
    """Near the end of a session, simulations stop within a round or two; the generator
    must still pause between them, or the terminal UI would wait for the whole forecast."""
    theta, cov = np.array([6.0, 4.0, 2.0, 0.0]), np.eye(4) * 1e-4
    steps = forecast_steps("exact", theta, cov, [0, 1, 2, 3], dict.fromkeys(range(4), 5), 1,
                           **FIXED)  # fmt: skip
    pauses = 0
    while True:
        try:
            next(steps)
            pauses += 1
        except StopIteration as finished:
            assert pauses >= finished.value.sims == 16
            break


def test_simulations_cut_short_give_a_floor_not_a_guess():
    f = forecast_rounds("exact", np.zeros(10), np.eye(10) * 2.25, list(range(10)), {}, 1, cap=3,
                        **FIXED)  # fmt: skip
    assert f.median is None and f.at_least == 3 and f.capped == f.sims


def test_service_reuses_a_forecast_until_the_list_changes(rk, conn):
    names = [f"item-{k}" for k in range(6)]
    rk.create_list("f", "F", names, seed=1, mode="quick")
    first = rk.forecast("f", budget_ms=200)
    assert rk.forecast("f").median == first.median
    assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 1
    run_rounds(rk, "f", SimulatedJudge({n: float(k) for k, n in enumerate(names)}, 2), 4)
    rk.forecast("f", budget_ms=200)
    rk.forecast("f", mode="exact", budget_ms=200)
    assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 3


def test_only_planned_lists_get_a_forecast(rk):
    rk.create_list("e", "E", ["a", "b", "c"], method="elo")
    rk.create_list("c", "C", ["a", "b", "c"], calibrate=True)
    assert rk.forecast("e") is None and rk.forecast("c") is None


def test_next_and_forecast_commands_show_rounds_left(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "f.db")
    items = tmp_path / "items.txt"
    items.write_text("A\nB\nC\nD\n", encoding="utf-8")
    runner.invoke(app, ["--db", db, "new", "f", "F", "--items", str(items), "--seed", "1"])
    out = runner.invoke(app, ["--db", db, "next", "f"]).output
    assert "rounds left" in out
    data = json.loads(runner.invoke(app, ["--db", db, "forecast", "f", "--json"]).output)
    assert data["mode"] == "stable" and data["sims"] >= 8
    assert json.loads(runner.invoke(app, ["--db", db, "next", "f", "--json", "--no-forecast"])
                      .output)["rounds_left"] is None  # fmt: skip
    rk_conn = store.connect(tmp_path / "f.db")
    assert rk_conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 1  # reused


@pytest.mark.perf
def test_forecast_stays_within_its_time_budget():
    theta, cov = np.zeros(200), np.eye(200) * 2.25
    f = forecast_rounds("exact", theta, cov, list(range(200)), {}, 1)
    assert f.ms < 1000 * 2 + 200  # the budget, plus the cut-off for a running simulation
