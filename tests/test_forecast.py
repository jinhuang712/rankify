"""Rounds left: the answers each pair the mode needs will take."""

import json
import math
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from typer.testing import CliRunner

from rankify import store
from rankify.cli.main import app
from rankify.engine.fit import DEFAULT_SIGMA_PRIOR
from rankify.engine.forecast import (
    Habits,
    _width_sd,
    forecast_rounds,
    later_bits,
    path_answers,
    score,
)
from rankify.engine.planner import ALL_KINDS, order_information_over
from rankify.service import _sharpness, _sharpness_belief, _sittings

from .conftest import SimulatedJudge, run_rounds


def _path(m0, v0, d, level=0.95, tie_ok=False, rel=1.0, tie=0.0):
    one = np.ones(1)
    n, m, prec = path_answers(
        m0 * one, v0 * one, d * one, level * one, np.array([tie_ok]), rel * one, tie
    )
    return float(n[0]), float(m[0]), float(prec[0])


def test_the_score_and_its_slope_are_davidsons():
    """G is the derivative of log(e^(m/2) + e^(-m/2) + nu), the model's expected score, and
    H is G's slope: the information of one answer. Without ties H is p(1 - p)."""
    m, nu, h = np.linspace(-4, 4, 9), 0.3, 1e-5

    def log_z(x):
        return np.log(np.exp(x / 2) + np.exp(-x / 2) + nu)

    g, slope = score(m, nu)
    np.testing.assert_allclose(g, (log_z(m + h) - log_z(m - h)) / (2 * h), atol=1e-8)
    np.testing.assert_allclose(
        slope, (score(m + h, nu)[0] - score(m - h, nu)[0]) / (2 * h), atol=1e-7
    )
    p = 1 / (1 + np.exp(-m))
    np.testing.assert_allclose(score(m, 0.0)[1], p * (1 - p), atol=1e-12)


def test_the_path_is_the_fits_estimate_after_those_answers():
    """After n answers at the judge's rates, the estimate solves the Laplace equation
    (m - m0) / v0 = n (drive - G(m)), and the precision is 1 / v0 + n H(m)."""
    m0, v0, d, nu = 0.2, 1.5, 1.0, 0.2
    n, m, prec = _path(m0, v0, d, level=0.99, tie=nu)
    a, b = math.exp(d / 2), math.exp(-d / 2)
    drive = (a - b) / (2 * (a + b + nu))
    g, h = score(np.array([m]), nu)
    assert 0 < n < math.inf and m0 < m < d
    at_m = (m - m0) / v0 / (drive - g[0])  # the answers that put the estimate at m
    assert prec == pytest.approx(1 / v0 + at_m * h[0], rel=1e-9)
    assert at_m / 1.05 < n <= at_m  # read halfway between the last two points


def test_a_pair_already_confident_needs_no_answers():
    assert _path(3.0, 0.25, 3.0)[0] == 0.0


def test_a_clear_judge_settles_a_pair_in_a_few_answers():
    """A judge who always picks the same item: a handful of answers settle it, as the real
    fit does. The information at the true gap (tiny when answers are predictable) would
    ask for hundreds."""
    n, _, _ = _path(0.0, 1.0, 12.0)
    assert 2 <= n <= 8


def test_closer_pairs_take_more_answers():
    needed = [_path(0.0, 1.0, d)[0] for d in (2.0, 1.0, 0.5, 0.0)]
    assert needed == sorted(needed) and needed[0] > 0


def test_equal_items_end_as_a_tie_or_at_the_floor():
    """Two equal items are never confidently ordered. Where a tie counts, a confident tie
    can end it; either way the floor does, sooner if the pair matters less, at once if it
    doesn't matter at all."""
    tie = _path(0.0, 1.0, 0.0, tie_ok=True, tie=0.3)[0]
    floor = _path(0.0, 1.0, 0.0, tie=0.3)[0]
    assert math.isfinite(tie) and tie <= floor
    assert _path(0.0, 1.0, 0.0, rel=0.5, tie=0.3)[0] < floor
    assert _path(0.0, 1.0, 0.0, rel=0.0, tie=0.3)[0] == 0.0


def test_the_floor_table_decides_as_the_exact_sum_does():
    rng = np.random.default_rng(2)
    mu, var = rng.uniform(-6, 6, 3000), 10 ** rng.uniform(-3.5, 1.2, 3000)
    table = later_bits(mu, var) < 0.1
    exact = order_information_over(mu, var, 8) < 0.1
    assert np.mean(table != exact) < 0.005


def test_the_width_is_as_unsure_as_its_hyperprior_before_any_answers():
    assert _width_sd(np.eye(6) * 1.5**2, 1.5) == pytest.approx(DEFAULT_SIGMA_PRIOR.sd)
    assert _width_sd(np.eye(6) * 0.1, 1.5) < 0.35  # every item pinned down


def test_orderings_finish_in_fewer_rounds_than_pairs():
    theta, cov = np.zeros(10), np.eye(10) * 2.25
    pairs = forecast_rounds("stable", theta, cov, list(range(10)), {}, 3)
    mixed = forecast_rounds("stable", theta, cov, list(range(10)), {}, 3, kinds=ALL_KINDS)
    assert mixed.median < pairs.median


def test_a_tired_judge_needs_more_rounds():
    """Tiredness only: the same list, a fresh judge against one already 30 calls into a
    sitting whose noise grows 2% per call."""
    theta, cov = np.linspace(2, -2, 8), np.eye(8) * 0.5
    looks = dict.fromkeys(range(8), 2)

    def rounds(habits, effort):
        kw = {"habits": habits, "effort": effort, "past_efforts": []}
        return forecast_rounds("exact", theta, cov, list(range(8)), looks, 1, **kw).median

    assert rounds(Habits(fatigue=0.02), 30) > 1.1 * rounds(Habits(fatigue=0.0), 0)


def test_a_sharper_judge_needs_fewer_rounds():
    theta, cov = np.linspace(2, -2, 8), np.eye(8) * 0.5
    looks = dict.fromkeys(range(8), 2)

    def rounds(sharpness):
        habits = Habits(sharpness=sharpness)
        return forecast_rounds("exact", theta, cov, list(range(8)), looks, 1, habits=habits).median

    assert rounds(3.0) < rounds(1.0)


def test_long_lists_count_items_that_are_already_out_of_reach_as_done():
    """With 60 items and the top three clear, the others need no more answers for Quick."""
    theta = np.concatenate([[6.0, 5.0, 4.0], np.linspace(0, -3, 57)])
    cov = np.eye(60) * 0.3
    f = forecast_rounds("quick", theta, cov, list(range(60)), dict.fromkeys(range(60), 3), 1)
    assert f.median is not None and f.median <= 5


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


def test_sharpness_is_unsure_until_answers_say_much():
    rng = np.random.default_rng(6)
    answers = []
    for _ in range(300):
        mu, sd = rng.normal(0, 1.5), 0.3
        truth = rng.normal(mu, np.sqrt(2) * sd)
        won = 1 if rng.random() < 1 / (1 + np.exp(-truth)) else 2
        answers.append(("pair", [1, 2], [won], {1: (mu, sd), 2: (0.0, sd)}))
    assert _sharpness_belief([]) == (1.0, 0.5)
    few, many = _sharpness_belief(answers[:10])[1], _sharpness_belief(answers)[1]
    assert many < few <= 0.5 and many < 0.15


def test_an_unsure_sharpness_widens_the_range():
    theta, cov = np.linspace(2, -2, 10), np.eye(10) * 0.8
    looks = dict.fromkeys(range(10), 2)
    sure = forecast_rounds("stable", theta, cov, list(range(10)), looks, 1, habits=Habits())
    unsure = forecast_rounds(
        "stable", theta, cov, list(range(10)), looks, 1, habits=Habits(sharpness_sd=0.5)
    )
    assert unsure.high - unsure.low > sure.high - sure.low


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
    f = forecast_rounds("exact", theta, cov, [0, 1, 2, 3], dict.fromkeys(range(4), 5), 1)
    assert (f.median, f.low, f.high) == (0, 0, 0)


def test_the_forecast_is_repeatable_and_shrinks_as_answers_come_in():
    theta, cov = np.zeros(8), np.eye(8) * 2.25
    early = forecast_rounds("stable", theta, cov, list(range(8)), {}, 7)
    again = forecast_rounds("stable", theta, cov, list(range(8)), {}, 7)
    assert (early.median, early.low, early.high) == (again.median, again.low, again.high)
    assert early.low <= early.median <= early.high
    spread = np.linspace(3, -3, 8)
    later = forecast_rounds(
        "stable", spread, np.eye(8) * 0.3, list(range(8)), dict.fromkeys(range(8), 4), 7
    )
    assert later.median < early.median


def test_draws_past_the_cap_give_a_floor_not_a_guess():
    f = forecast_rounds("exact", np.zeros(10), np.eye(10) * 2.25, list(range(10)), {}, 1, cap=3)
    assert f.median is None and f.at_least == 3 and f.capped == f.draws


def test_service_reuses_a_forecast_until_the_list_changes(rk, conn):
    names = [f"item-{k}" for k in range(6)]
    rk.create_list("f", "F", names, seed=1, mode="quick")
    first = rk.forecast("f")
    assert rk.forecast("f").median == first.median
    assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 1
    run_rounds(rk, "f", SimulatedJudge({n: float(k) for k, n in enumerate(names)}, 2), 4)
    rk.forecast("f")
    rk.forecast("f", mode="exact")
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
    assert data["mode"] == "stable" and data["draws"] == 64
    assert json.loads(runner.invoke(app, ["--db", db, "next", "f", "--json", "--no-forecast"])
                      .output)["rounds_left"] is None  # fmt: skip
    rk_conn = store.connect(tmp_path / "f.db")
    assert rk_conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 1  # reused


@pytest.mark.perf
@pytest.mark.parametrize(
    ("mode", "k", "limit_ms"), [("stable", 20, 30), ("stable", 50, 80), ("exact", 200, 2000)]
)
def test_the_forecast_takes_milliseconds(mode, k, limit_ms):
    rng = np.random.default_rng(1)
    theta, cov = rng.normal(0, 1.5, k), np.eye(k) * 0.5
    forecast_rounds(mode, theta, cov, list(range(k)), {}, 1)  # the floor table, once
    f = forecast_rounds(mode, theta, cov, list(range(k)), {}, 1)
    assert f.ms < limit_ms
