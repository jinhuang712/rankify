import numpy as np
import pytest

from rankify.service import RankifyError

from .conftest import SimulatedJudge, kendall_tau, run_rounds

NAMES = ["Kyoto", "Lisbon", "Reykjavik", "Cape Town", "Buenos Aires"]


def test_new_list_ranks_every_item_equally(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    view = rk.ranking("travel")
    assert view.answers == 0
    assert sorted(i.name for i in view.items) == sorted(NAMES)
    assert all(i.score == pytest.approx(1500) for i in view.items)
    assert all(i.could_be == (1, 5) for i in view.items)


def test_next_round_stays_open_until_answered(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    first = rk.next_round("travel")
    assert rk.next_round("travel") == first
    rk.answer("travel", [1])
    assert rk.next_round("travel").round == first.round + 1


def test_answer_moves_the_winner_up(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    view = rk.next_round("travel")
    winner, loser = view.items[1].name, view.items[0].name
    rk.answer("travel", [2])
    ranking = {i.name: i for i in rk.ranking("travel").items}
    assert ranking[winner].score > 1500 > ranking[loser].score


def test_answer_checks_round_and_numbers(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    with pytest.raises(RankifyError, match="no round"):
        rk.answer("travel", [1])
    view = rk.next_round("travel")
    with pytest.raises(RankifyError, match="not open"):
        rk.answer("travel", [1], round_seq=view.round + 5)
    with pytest.raises(RankifyError):
        rk.answer("travel", [3])
    with pytest.raises(RankifyError):
        rk.answer("travel", [1], cant_decide=True)
    rk.answer("travel", [2, 1], round_seq=view.round)


def test_cant_decide_is_an_answer(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    rk.next_round("travel")
    rk.answer("travel", cant_decide=True)
    ranking = rk.ranking("travel")
    assert ranking.answers == 1
    assert all(i.score == pytest.approx(1500, abs=1e-6) for i in ranking.items)


def test_undo_cancels_and_asks_again(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    before = rk.ranking("travel")
    asked = rk.next_round("travel")
    rk.answer("travel", [1])
    again = rk.undo("travel")
    assert [i.name for i in again.items] == [i.name for i in asked.items]
    assert again.round > asked.round
    after = rk.ranking("travel")
    assert after.answers == 0
    assert {i.name: i.score for i in after.items} == pytest.approx(
        {i.name: i.score for i in before.items}, abs=1e-6
    )
    with pytest.raises(RankifyError, match="nothing to undo"):
        rk.undo("travel")


def test_removed_item_is_hidden_but_its_answers_count(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    view = rk.next_round("travel")
    loser = view.items[1].name
    rk.answer("travel", [1])
    rk.remove_item("travel", loser)
    ranking = rk.ranking("travel")
    assert loser not in [i.name for i in ranking.items]
    assert ranking.answers == 1
    assert ranking.items[0].name == view.items[0].name


def test_added_item_starts_in_the_middle(rk):
    rk.create_list("travel", "Places", NAMES, seed=1)
    run_rounds(rk, "travel", SimulatedJudge(dict(zip(NAMES, range(5))), seed=2), 10)
    rk.add_item("travel", "Hanoi")
    hanoi = next(i for i in rk.ranking("travel").items if i.name == "Hanoi")
    assert hanoi.score == pytest.approx(1500, abs=60)
    assert hanoi.could_be[1] - hanoi.could_be[0] >= 3


def test_duplicate_and_bad_names_are_rejected(rk):
    with pytest.raises(RankifyError):
        rk.create_list("Bad Name", "x")
    with pytest.raises(RankifyError):
        rk.create_list("dups", "x", ["A", "A"])
    rk.create_list("travel", "Places", NAMES, seed=1)
    with pytest.raises(RankifyError, match="already"):
        rk.add_item("travel", "Kyoto")
    with pytest.raises(RankifyError, match="already exists"):
        rk.create_list("travel", "Again")


def test_verify_passes_then_catches_tampering(rk, conn):
    rk.create_list("travel", "Places", NAMES, seed=1)
    run_rounds(rk, "travel", SimulatedJudge(dict(zip(NAMES, range(5))), seed=3), 25)
    assert rk.verify("travel") == []
    conn.execute(
        "UPDATE fit_items SET theta = theta + 0.5 WHERE fit_id = (SELECT MAX(id) FROM fits)"
    )
    assert any("theta" in p for p in rk.verify("travel"))


def test_replay_gives_the_same_rounds(rk):
    """Sanity check 4: the same seed and answers give the same rounds."""
    truth = {n: float(k) for k, n in enumerate(NAMES)}
    rk.create_list("one", "Places", NAMES, seed=42)
    rk.create_list("two", "Places", NAMES, seed=42)
    first = run_rounds(rk, "one", SimulatedJudge(truth, seed=9), 30)
    second = run_rounds(rk, "two", SimulatedJudge(truth, seed=9), 30)
    assert first == second


def test_simulated_judge_ranking_matches_the_truth(rk):
    """The ranking works: a noisy judge's answers recover the true order, with honest ranges."""
    rng = np.random.default_rng(5)
    names = [f"item-{k:02d}" for k in range(12)]
    truth = dict(zip(names, rng.normal(0, 1.5, len(names))))
    rk.create_list("sim", "Simulated", names, seed=7)
    run_rounds(rk, "sim", SimulatedJudge(truth, seed=6), 250, mode="exact")
    ranking = rk.ranking("sim")
    order = [i.name for i in ranking.items]
    assert kendall_tau(order, truth) >= 0.8
    true_rank = {
        n: r + 1 for r, n in enumerate(sorted(names, key=lambda n: truth[n], reverse=True))
    }
    covered = sum(i.could_be[0] <= true_rank[i.name] <= i.could_be[1] for i in ranking.items)
    assert covered >= 10  # nominal 90% of 12
    assert rk.verify("sim") == []
