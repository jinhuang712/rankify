"""The benchmark's extra judges, reference sort and planner variants."""

import itertools
import math

import numpy as np
import pytest

from rankify.bench import (
    CARELESS_LAPSE,
    JUDGES,
    Judge,
    add_twins,
    hidden_scores,
    run_one,
)
from rankify.engine.baselines import ford_johnson_pair
from rankify.engine.model import A_WINS, B_WINS
from rankify.service import NothingToAsk, RankifyError

from .conftest import SimulatedJudge


def _first_wins(kind: str, diff: float, rounds: int = 4000, round_no: int = 0) -> float:
    judge = Judge({"a": diff, "b": 0.0}, kind, np.random.default_rng(1))
    return float(np.mean([judge.answer(["a", "b"], round_no)[0] == 1 for _ in range(rounds)]))


@pytest.mark.parametrize("n", [2, 3, 5, 10, 20])
def test_ford_johnson_sorts_a_perfect_judge_within_its_known_count(n):
    bound = sum(math.ceil(math.log2(3 * k / 4)) for k in range(1, n + 1))  # 22 for 10, 62 for 20
    for seed in range(10):
        truth = np.random.default_rng(seed).normal(size=n)
        history, out = [], []
        while (pair := ford_johnson_pair(list(range(n)), history, seed, out)) is not None:
            a, b = pair
            history.append((a, b, A_WINS if truth[a] > truth[b] else B_WINS))
        assert out == sorted(range(n), key=lambda i: -truth[i])
        assert len(history) <= bound


def test_ford_johnson_runs_through_the_service(rk):
    names = [f"item-{k}" for k in range(8)]
    rk.create_list("fj", "FJ", names, seed=4, method="ford-johnson")
    judge = SimulatedJudge({n: 10.0 * k for k, n in enumerate(names)}, 1)  # all but perfect
    asked = 0
    with pytest.raises(NothingToAsk):
        while True:
            view = rk.next_round("fj")
            rk.answer("fj", judge.answer(view.kind, [i.name for i in view.items]))
            asked += 1
    assert asked <= 16  # Ford-Johnson's count for 8 items
    assert [i.name for i in rk.ranking("fj").items] == names[::-1]


def test_planner_variants_are_for_benchmarking_pairs(rk):
    rk.create_list("c", "C", ["a", "b", "c", "d"], seed=1, planner="closest")
    rk.create_list("p", "P", ["a", "b", "c", "d"], seed=1, planner="per-round")
    assert rk.next_round("c").kind == "pair" and rk.next_round("p").kind == "pair"
    with pytest.raises(RankifyError):
        rk.create_list("m", "M", ["a", "b", "c"], rounds="mixed", planner="closest")
    with pytest.raises(RankifyError):
        rk.create_list("e", "E", ["a", "b", "c"], method="elo", planner="per-round")
    with pytest.raises(RankifyError):
        rk.create_list("x", "X", ["a", "b", "c"], planner="random")


def test_model_judges_tell_neighbours_apart_as_specified():
    """On lists of the benchmark's shape, the median neighbour accuracy is about 90%, 75%
    and 60% for sharp, normal and fuzzy, and thurstone is as accurate as normal."""
    rng = np.random.default_rng(2)
    for kind, target in (("sharp", 0.90), ("normal", 0.75), ("fuzzy", 0.60), ("thurstone", 0.75)):
        medians = []
        for _ in range(60):
            theta = hidden_scores([f"i{k}" for k in range(20)], rng)
            order = sorted(theta, key=lambda x: -theta[x])
            judge = Judge(theta, kind, rng)
            right = [
                np.mean([judge.answer([a, b], 0)[0] == 1 for _ in range(60)])
                for a, b in itertools.pairwise(order)
            ]
            medians.append(float(np.median(right)))
        assert float(np.median(medians)) == pytest.approx(target, abs=0.05), kind


def test_each_twist_does_what_it_says():
    assert _first_wins("normal", 0.0) == pytest.approx(0.5, abs=0.03)
    assert _first_wins("biased", 0.0) == pytest.approx(0.6, abs=0.03)
    careless = _first_wins("careless", 5.0)  # a sure call, answered at random 5% of the time
    assert careless == pytest.approx(1 - CARELESS_LAPSE / 2, abs=0.015)
    fresh, tired = _first_wins("tired", 0.3), _first_wins("tired", 0.3, round_no=300)
    assert fresh > 0.75 and tired < fresh - 0.1


def test_twins_split_the_vote_in_a_pick():
    """Luce's axiom says each of three equal items wins a pick a third of the time. With
    two of them twins, the twins share one option's chance, so the third wins half."""
    theta = {"a": 0.0, "a2": 0.0, "b": 0.0}
    judge = Judge(theta, "similar", np.random.default_rng(3), twins={"a": 0, "a2": 0})
    picks = [judge.answer_set(["a", "a2", "b"], "pick", 0)[0][0] for _ in range(4000)]
    assert np.mean(np.array(picks) == 3) == pytest.approx(0.5, abs=0.03)


def test_add_twins_pairs_up_a_quarter_of_the_items():
    theta = hidden_scores([f"i{k}" for k in range(20)], np.random.default_rng(5))
    twins = add_twins(theta, np.random.default_rng(6))
    assert len(twins) == 6  # a quarter of 20 is 5 items, rounded up to 3 twin pairs
    for g in set(twins.values()):
        a, b = (name for name, h in twins.items() if h == g)
        assert abs(theta[a] - theta[b]) < 0.05


@pytest.mark.parametrize("judge", [j for j in JUDGES if j not in ("human", "perfect", "noisy")])
def test_every_new_judge_runs_a_benchmark_session(judge):
    res = run_one("rankify:quick", judge, 6, seed=3, budget=30)
    assert res.rounds > 0 and not res.error


@pytest.mark.parametrize(
    "method", ["rankify-closest:quick", "rankify-per-round:quick", "ford-johnson"]
)
def test_variants_and_ford_johnson_run_a_benchmark_session(method):
    res = run_one(method, "normal", 6, seed=3, budget=30)
    assert res.rounds > 0 and res.forecasts == []
