import json
import math

import numpy as np
import pytest
from typer.testing import CliRunner

from rankify.bench import (
    DEFAULT_METHODS,
    TIE_MARGIN,
    Judge,
    first_confirmed,
    kendall_tau,
    run_one,
    targets_met,
)
from rankify.cli.main import app
from rankify.engine.baselines import (
    LogMismatch,
    elo_ratings,
    glicko2_ratings,
    insertion_sort,
    just_sort_it_pair,
    openskill_ratings,
    trueskill_ratings,
)
from rankify.engine.model import A_WINS, B_WINS, TIE


def answer_perfectly(pair, truth):
    return A_WINS if truth[pair[0]] > truth[pair[1]] else B_WINS


def test_insertion_sort_with_a_perfect_judge_sorts_exactly():
    rng = np.random.default_rng(0)
    truth = rng.normal(size=12)
    items, history = list(range(12)), []
    while (state := insertion_sort(items, history, seed=5)).next_pair:
        history.append((*state.next_pair, answer_perfectly(state.next_pair, truth)))
    assert state.ranked == list(np.argsort(-truth))
    assert len(history) <= sum(math.ceil(math.log2(k + 1)) for k in range(12))


def test_just_sort_it_replays_its_own_log():
    truth = np.arange(6.0)
    history = []
    for _ in range(40):
        pair = just_sort_it_pair(list(range(6)), history, seed=3)
        history.append((*pair, answer_perfectly(pair, truth)))
    assert just_sort_it_pair(list(range(6)), history, seed=3) == just_sort_it_pair(
        list(range(6)), history, seed=3
    )
    with pytest.raises(LogMismatch):
        just_sort_it_pair(list(range(6)), [(history[0][1], history[0][0], A_WINS)], seed=3)


def test_online_rating_systems_depend_on_answer_order():
    log = [(0, 1, A_WINS), (1, 2, A_WINS), (2, 0, A_WINS), (0, 1, TIE)]
    assert not np.allclose(elo_ratings(3, log), elo_ratings(3, log[::-1]))
    for ratings in (glicko2_ratings, trueskill_ratings, openskill_ratings):
        theta, sd = ratings(3, log)
        assert theta.shape == sd.shape == (3,)
        assert np.all(sd > 0)
        assert not np.allclose(theta, ratings(3, log[::-1])[0])


def test_rating_systems_put_the_winner_on_top():
    log = [(0, 1, A_WINS)] * 5 + [(1, 2, A_WINS)] * 5
    for ratings in (glicko2_ratings, trueskill_ratings, openskill_ratings):
        theta, _ = ratings(3, log)
        assert list(np.argsort(-theta)) == [0, 1, 2]


def test_baseline_methods_run_through_the_cli(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "b.db")
    items = tmp_path / "items.txt"
    items.write_text("A\nB\nC\nD\n", encoding="utf-8")
    truth = {"A": 4, "B": 3, "C": 2, "D": 1}
    runner.invoke(
        app,
        [
            "--db",
            db,
            "new",
            "s",
            "S",
            "--items",
            str(items),
            "--method",
            "insertion-sort",
            "--seed",
            "1",
        ],
    )
    result = None
    for _ in range(20):
        result = runner.invoke(app, ["--db", db, "next", "s", "--json"])
        if result.exit_code == 3:
            break
        names = [i["name"] for i in json.loads(result.stdout)["items"]]
        runner.invoke(
            app, ["--db", db, "answer", "s", "1" if truth[names[0]] > truth[names[1]] else "2"]
        )
    assert result is not None and result.exit_code == 3
    ranking = json.loads(runner.invoke(app, ["--db", db, "show", "s", "--json"]).stdout)
    assert [i["name"] for i in ranking["items"]] == ["A", "B", "C", "D"]
    assert ranking["items"][0]["could_be"] is None
    assert runner.invoke(app, ["--db", db, "verify", "s"]).exit_code == 0
    assert runner.invoke(app, ["--db", db, "add", "s", "E"]).exit_code == 1

    runner.invoke(app, ["--db", db, "new", "e", "E", "--items", str(items), "--method", "elo"])
    runner.invoke(app, ["--db", db, "next", "e"])
    runner.invoke(app, ["--db", db, "answer", "e", "1"])
    ranking = json.loads(runner.invoke(app, ["--db", db, "show", "e", "--json"]).stdout)
    assert ranking["method"] == "elo"
    assert sorted(i["score"] for i in ranking["items"]) == [1484.0, 1500.0, 1500.0, 1516.0]
    assert runner.invoke(app, ["--db", db, "verify", "e"]).exit_code == 0


def test_targets_and_convergence():
    theta = {"a": 6.0, "b": 5.0, "c": 4.0, "d": 3.0, "e": 2.0, "f": 1.0}
    assert targets_met(list("abcdef"), theta) == {"quick": True, "stable": True, "exact": True}
    assert targets_met(list("abcdfe"), theta) == {"quick": True, "stable": True, "exact": False}
    assert targets_met(list("bacdef"), theta)["quick"] is False
    near = theta | {"b": 6.0 - TIE_MARGIN / 2}  # a and b are a near-tie: a swap is not an error
    assert targets_met(list("bacdef"), near)["exact"] is True
    assert kendall_tau(list("abcdef"), theta) == 1.0
    assert kendall_tau(list("fedcba"), theta) == -1.0
    assert first_confirmed([False] + [True] * 11, finished=False) == 2
    assert first_confirmed([False, True, True], finished=True) == 2
    assert first_confirmed([False, True, True], finished=False) is None


def test_human_judge_behaves_like_a_person():
    theta = {"far-top": 3.0, "far-bottom": -3.0, "twin-1": 0.0, "twin-2": 0.01}
    judge = Judge(theta, "human", np.random.default_rng(0))
    easy = [judge.answer(["far-top", "far-bottom"], 0) for _ in range(400)]
    hard = [judge.answer(["twin-1", "twin-2"], 0) for _ in range(400)]
    assert np.mean([a == 1 for a, _ in easy]) > 0.95  # only lapses go wrong
    assert np.mean([a is None for a, _ in hard]) > 0.15  # often unsure on near-ties
    assert np.mean([s for _, s in hard]) > np.mean([s for _, s in easy]) + 1  # slower when close
    perfect = Judge(theta, "perfect", np.random.default_rng(0))
    assert all(perfect.answer(["twin-2", "twin-1"], k)[0] == 1 for k in range(50))


@pytest.mark.parametrize("method", DEFAULT_METHODS)
def test_benchmark_run_through_the_cli(method):
    res = run_one(method, "human", 6, seed=11, budget=40)
    assert res.rounds > 0
    assert len(res.taus) == res.rounds == len(res.implied) == len(res.seconds)
    if method == "insertion-sort":
        assert res.finished
