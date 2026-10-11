"""Rounds left: the simulated rest of the session."""

import json
import math

import numpy as np
import pytest
from typer.testing import CliRunner

from rankify import store
from rankify.cli.main import app
from rankify.engine.fit import fit_pairs
from rankify.engine.forecast import _update, forecast_rounds, forecast_steps
from rankify.engine.model import A_WINS, Pairs, Prior

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
