import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from typer.testing import CliRunner

from rankify.bench import Judge, hidden_scores, targets_met
from rankify.cli.main import app
from rankify.engine.fit import fit_pairs_learning_sigma
from rankify.engine.model import A_WINS, B_WINS, Pairs
from rankify.engine.planner import MIN_LOOKS, Timing, order_information
from rankify.service import NothingToAsk, Rankify, RankifyError

from .conftest import first_listed


def answer_as(judge: Judge, rk: Rankify, slug: str, view, t: int) -> None:
    """Answer any kind of round as the benchmark's simulated judge would."""
    names = [i.name for i in view.items]
    if view.kind == "pair":
        pick, secs = judge.answer(names, t)
        numbers = None if pick is None else [pick]
    else:
        numbers, secs = judge.answer_set(names, view.kind, t)
    rk.answer(slug, numbers, cant_decide=numbers is None, ms=int(secs * 1000))


def test_order_information_ignores_settled_pairs_and_known_ties():
    mu = np.array([0.0, 3.0, 0.0])
    var = np.array([3.0, 0.1, 0.0001])
    info = order_information(mu, var)
    assert info[0] > 0.15  # unexplored pair: worth asking
    assert info[1] < 1e-3  # order already settled
    assert info[2] < 1e-3  # known to be a tie: its answer is a coin flip that teaches nothing


def test_learned_width_grows_for_a_consistent_judge():
    rng = np.random.default_rng(0)
    theta = 2.0 * rng.standard_normal(12)
    a = rng.integers(0, 12, 200)
    b = (a + rng.integers(1, 12, 200)) % 12
    perfect = np.where(theta[a] > theta[b], A_WINS, B_WINS)
    coin = rng.integers(0, 2, 200)
    assert fit_pairs_learning_sigma(12, Pairs.of(a, b, perfect)).sigma > 3.0
    assert fit_pairs_learning_sigma(12, Pairs.of(a, b, coin)).sigma < 1.0


def test_many_answers_are_worth_more_than_one_but_not_for_ties():
    from rankify.engine.planner import order_information_over

    mu = np.array([0.0, 0.0, 2.6])
    var = np.array([0.4, 0.01, 0.2])
    np.testing.assert_allclose(
        order_information_over(mu, var, 1), order_information(mu, var), atol=1e-12
    )
    eight = order_information_over(mu, var, 8)
    assert eight[0] > 0.2  # unsure: eight answers add up
    assert eight[1] < 0.02 and eight[2] < 1e-3  # a known tie or a settled order: still nothing


def test_quick_target_needs_every_lower_item_out_of_reach():
    from rankify.engine import stop

    theta = np.array([3.0, 2.0, 1.0, 0.0, -1.0])
    cov = np.eye(5) * 0.001
    nb = stop.neighbours(theta, cov, [0, 1, 2, 3, 4])
    settled = [(0, 1, 1), (1, 2, 2), (2, 3, 3), (3, 4, 4), (4, 5, 5)]
    reachable = [(0, 1, 1), (1, 2, 2), (2, 3, 3), (3, 4, 4), (4, 2, 5)]  # #5 could be #2
    assert stop.target_reached("quick", nb, settled)
    assert not stop.target_reached("quick", nb, reachable)


@pytest.mark.parametrize("rounds", ["mixed", "pairs"])
def test_every_item_gets_first_looks_before_it_is_judged(rk, rounds):
    names = [f"item-{k}" for k in range(8)]
    rk.create_list("f", "F", names, seed=4, mode="quick", rounds=rounds)
    looks = dict.fromkeys(names, 0)
    for _ in range(20):
        view = rk.next_round("f")
        if rk.why("f", view.round).reason != "first look":
            break
        for item in view.items:
            looks[item.name] += 1
        rk.answer("f", first_listed(view))
    else:
        raise AssertionError("first looks never ended")
    assert min(looks.values()) >= MIN_LOOKS


def test_a_best_item_that_loses_its_first_comparison_is_still_found():
    """Regression: on a crowded list, the clearly best item lost its first comparison to a
    slip and the planner stopped before looking at it again."""
    seed = 20009
    names = [f"item-{k:02d}" for k in range(20)]
    theta = hidden_scores(names, np.random.default_rng(seed))
    judge = Judge(theta, "human", np.random.default_rng([seed, 1]))
    rk = Rankify(__import__("rankify").store.connect(":memory:"))
    rk.create_list("q", "Q", names, seed=seed, mode="quick")
    for t in range(400):
        try:
            view = rk.next_round("q")
        except NothingToAsk:
            break
        answer_as(judge, rk, "q", view, t)
    best = max(names, key=lambda x: theta[x])
    assert [i.name for i in rk.ranking("q").items][:3].count(best) == 1


def test_learned_width_converges_from_far_away():
    """Regression: a perfect judge's answers put the best width far above the 1.5 start,
    where Aitken's extrapolation used to run the wrong way and never converge."""
    import math
    from dataclasses import replace

    from rankify.engine.fit import DEFAULT_SIGMA_PRIOR, _best_log_sigma, fit_pairs
    from rankify.engine.model import Prior

    rng = np.random.default_rng(20000)
    theta = 6.0 * rng.standard_normal(20)
    a = rng.integers(0, 20, 250)
    b = (a + rng.integers(1, 20, 250)) % 20
    pairs = Pairs.of(a, b, np.where(theta[a] > theta[b], A_WINS, B_WINS))
    s, x = math.log(1.5), None
    for _ in range(300):  # plain EM, slowly but surely, for reference
        f = fit_pairs(20, pairs, replace(Prior(), sigma=math.exp(s)), x0=x)
        spread = float(np.sum(f.theta**2) + np.trace(f.theta_cov))
        s, x = _best_log_sigma(spread, 20, s, DEFAULT_SIGMA_PRIOR), f.x
    fast = fit_pairs_learning_sigma(20, pairs)
    assert fast.sigma > 5.0
    assert fast.sigma == pytest.approx(math.exp(s), rel=1e-8)
    assert fast.iterations < 60


def test_learned_width_converges_with_almost_no_answers():
    """Regression: 200 items and one answer made plain EM crawl and never converge."""
    fit = fit_pairs_learning_sigma(200, Pairs.of([0], [1], [B_WINS]))
    assert 1.0 < fit.sigma < 2.0  # the hyperprior's centre, barely moved
    assert fit.iterations < 30


@settings(max_examples=25, deadline=None)
@given(st.integers(0, 10_000), st.randoms(use_true_random=False))
def test_learned_width_does_not_depend_on_answer_order_or_start(seed, rnd):
    rng = np.random.default_rng(seed)
    n, m = 8, 40
    a = rng.integers(0, n, m)
    b = (a + rng.integers(1, n, m)) % n
    y = rng.integers(0, 3, m)
    fit = fit_pairs_learning_sigma(n, Pairs.of(a, b, y))
    perm = list(range(m))
    rnd.shuffle(perm)
    shuffled = fit_pairs_learning_sigma(
        n, Pairs.of(a[perm], b[perm], y[perm]), x0=fit.x + 0.3, sigma0=fit.sigma * 2
    )
    np.testing.assert_allclose(shuffled.x, fit.x, atol=1e-8)
    assert shuffled.sigma == pytest.approx(fit.sigma, abs=1e-8)


def test_timing_learns_that_close_calls_take_longer():
    rng = np.random.default_rng(1)
    z = rng.uniform(0, 3, 200)
    seconds = 2.0 + 3.0 * np.exp(-z / 0.5) + rng.normal(0, 0.2, 200)
    t = Timing.fit(list(zip(z, seconds, strict=True)))
    assert t.base == pytest.approx(2.0, abs=0.3)
    assert t.close == pytest.approx(3.0, abs=0.5)
    assert Timing.fit([(0.1, 4.0)] * 5).close == 0.0  # too few answers: a flat guess


@pytest.mark.parametrize("mode", ["quick", "stable", "exact"])
def test_perfect_judge_session_stops_with_the_target_really_met(mode):
    rng = np.random.default_rng(3)
    names = [f"item-{k:02d}" for k in range(10)]
    theta = hidden_scores(names, rng, 3.0)
    judge = Judge(theta, "perfect", np.random.default_rng(4))
    rk = Rankify(__import__("rankify").store.connect(":memory:"))
    rk.create_list("p", "P", names, seed=2, mode=mode)
    asked = []
    for t in range(300):
        try:
            view = rk.next_round("p")
        except NothingToAsk as e:
            assert "target reached" in str(e)
            break
        asked.append(frozenset(i.name for i in view.items))
        answer_as(judge, rk, "p", view, t)
    else:
        raise AssertionError("never stopped")
    ranking = rk.ranking("p")
    assert ranking.target_reached is True
    assert targets_met([i.name for i in ranking.items], theta)[mode]
    assert len(asked) < 120
    assert rk.verify("p") == []


def test_why_explains_a_planned_round_and_mode_can_be_overridden(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "w.db")
    items = tmp_path / "items.txt"
    items.write_text("A\nB\nC\nD\nE\n", encoding="utf-8")
    runner.invoke(app, ["--db", db, "new", "w", "W", "--items", str(items), "--seed", "5"])
    round_ = json.loads(runner.invoke(app, ["--db", db, "next", "w", "--json"]).stdout)
    result = runner.invoke(app, ["--db", db, "why", "w", "--round", str(round_["round"])])
    assert result.exit_code == 0, result.output
    assert "Learns" in result.output and "→" in result.output
    data = json.loads(
        runner.invoke(
            app, ["--db", db, "why", "w", "--round", str(round_["round"]), "--json"]
        ).stdout
    )
    assert data["chosen"]["names"] == [i["name"] for i in round_["items"]]
    assert data["chosen"]["kind"] == round_["kind"]
    every = ["1"] if round_["kind"] == "pick" else [str(i["n"]) for i in round_["items"]]
    runner.invoke(app, ["--db", db, "answer", "w", *every, "--ms", "2500"])
    result = runner.invoke(app, ["--db", db, "next", "w", "--mode", "exact", "--json"])
    assert result.exit_code == 0, result.output
    rk = Rankify(__import__("rankify").store.connect(tmp_path / "w.db"))
    assert rk.why("w", json.loads(result.stdout)["round"]).mode == "exact"
    with pytest.raises(RankifyError):
        rk.next_round("w", mode="fastest")


def test_before_giving_up_every_item_still_in_play_gets_six_looks(monkeypatch):
    """When even the best pair looks worth too little, the planner first gives each item
    still in play TOPUP_LOOKS answers, least-seen first; only then is nothing worth asking."""
    from rankify.engine import planner

    monkeypatch.setattr(planner, "FLOOR_BITS", 100.0)  # nothing ever looks worth asking
    theta = np.linspace(2.0, -2.0, 12)
    cov = np.eye(12) * 1.0
    ranks = [(p, max(1, p - 3), min(12, p + 5)) for p in range(12)]
    looks = dict.fromkeys(range(12), planner.TOPUP_LOOKS)
    looks[5] = 2  # in play, barely seen
    plan = planner.plan_round("stable", theta, cov, ranks, planner.Timing(), 1, looks)
    assert plan.reason == "another look" and 5 in plan.chosen.items
    looks[5] = planner.TOPUP_LOOKS
    plan = planner.plan_round("stable", theta, cov, ranks, planner.Timing(), 1, looks)
    assert plan.chosen is None and plan.reason == "nothing worth asking"
