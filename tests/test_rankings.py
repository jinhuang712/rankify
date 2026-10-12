"""Plackett–Luce pick and rank rounds: the engine, the planner and the service."""

import choix
import numpy as np
import pytest

from rankify import store
from rankify.engine.fit import fit_pairs, fit_pairs_learning_sigma
from rankify.engine.model import (
    A_WINS,
    B_WINS,
    TIE,
    Choices,
    Pairs,
    Prior,
    grad_hess,
    log_posterior,
)
from rankify.engine.planner import (
    MIN_SET_SAMPLES,
    SET_TIME_GUESS,
    Timing,
    _fisher,
    order_information,
    plan_round,
    set_gain,
)
from rankify.service import NothingToAsk, RankifyError

from .conftest import SimulatedJudge, first_listed

NO_PAIRS = Pairs.of([], [], [])


def random_rounds(n, count, rng, theta=None):
    """Mixed pick and rank rounds of 3-5 items; answers follow Plackett-Luce if theta given."""
    rounds = []
    for _ in range(count):
        k = int(rng.integers(3, 6))
        shown = [int(v) for v in rng.choice(n, k, replace=False)]
        if theta is None:
            order = [int(v) for v in rng.permutation(shown)]
        else:  # sample a Plackett-Luce ordering with the Gumbel trick
            noisy = theta[shown] + rng.gumbel(size=k)
            order = [shown[i] for i in np.argsort(-noisy)]
        rounds.append((shown, order if rng.random() < 0.6 else order[:1]))
    return rounds


def test_gradient_and_hessian_match_finite_differences_with_pairs_and_choices():
    rng = np.random.default_rng(0)
    n = 7
    choices = Choices.of(random_rounds(n, 25, rng))
    pairs = Pairs.of([0, 1, 2, 3], [4, 5, 6, 0], [A_WINS, B_WINS, TIE, A_WINS])
    prior = Prior()
    x = rng.normal(0, 0.6, n + 2)
    g, h = grad_hess(x, n, pairs, prior, True, choices)
    eps = 1e-6
    for i in range(n + 2):
        e = np.zeros(n + 2)
        e[i] = eps
        fd = (
            log_posterior(x + e, n, pairs, prior, True, choices)
            - log_posterior(x - e, n, pairs, prior, True, choices)
        ) / (2 * eps)
        assert fd == pytest.approx(g[i], abs=1e-6)
        gp, _ = grad_hess(x + e, n, pairs, prior, True, choices)
        gm, _ = grad_hess(x - e, n, pairs, prior, True, choices)
        np.testing.assert_allclose((gp - gm) / (2 * eps), h[:, i], atol=1e-5)


def test_fit_matches_choix_on_pick_and_rank_rounds():
    rng = np.random.default_rng(1)
    n, sigma = 10, 1.5
    rounds = random_rounds(n, 120, rng, theta=rng.normal(0, 1.5, n))
    fit = fit_pairs(
        n, NO_PAIRS, Prior(sigma=sigma), ties=False, bias=False, choices=Choices.of(rounds)
    )
    top1 = []
    for shown, answer in rounds:
        if len(answer) == 1:
            top1.append((answer[0], [x for x in shown if x != answer[0]]))
        else:
            top1 += [(answer[r], answer[r + 1 :]) for r in range(len(answer) - 1)]
    ref = choix.opt_top1(n, top1, alpha=1 / (2 * sigma**2), tol=1e-12)
    np.testing.assert_allclose(fit.theta, ref, atol=1e-4)


def test_rank_rounds_recover_the_true_order():
    rng = np.random.default_rng(2)
    n = 12
    theta = np.linspace(2, -2, n)
    rounds = [
        (shown, order) for shown, order in random_rounds(n, 400, rng, theta) if len(order) > 1
    ]
    fit = fit_pairs_learning_sigma(n, NO_PAIRS, choices=Choices.of(rounds))
    tau = np.corrcoef(np.argsort(np.argsort(-fit.theta)), np.arange(n))[0, 1]
    assert tau > 0.95


def test_order_of_rounds_does_not_matter_with_choices():
    rng = np.random.default_rng(3)
    n = 9
    rounds = random_rounds(n, 40, rng, theta=rng.normal(0, 1, n))
    pairs = Pairs.of([0, 2, 4], [1, 3, 5], [A_WINS, B_WINS, TIE])
    one = fit_pairs_learning_sigma(n, pairs, choices=Choices.of(rounds))
    shuffled = [rounds[k] for k in rng.permutation(len(rounds))]
    two = fit_pairs_learning_sigma(n, pairs, choices=Choices.of(shuffled))
    np.testing.assert_allclose(one.x, two.x, atol=1e-8)


def test_a_rank_round_counts_as_several_choices():
    c = Choices.of([([4, 2, 7], [2, 7, 4]), ([1, 3, 5, 6], [5])])
    assert len(c) == 3  # 2 choices from the ranking of 3, 1 from the pick
    assert list(c.sets[0][:3]) == [2, 7, 4] and list(c.sets[1][:2]) == [7, 4]
    assert list(c.sets[2][:4]) == [5, 1, 3, 6]
    assert c.first[0][2] and c.first[2][1]  # item 4 and item 1 were shown first


def test_bad_rounds_are_rejected():
    with pytest.raises(ValueError):
        Choices.of([([1, 2, 3], [1, 2])])  # neither a pick nor a full order
    with pytest.raises(ValueError):
        Choices.of([([1, 2, 3, 4, 5, 6], [1])])  # more than 5 items
    with pytest.raises(ValueError):
        Choices.of([([1, 2, 3], [9])])  # answer not among the shown items


# ---------------------------------------------------------------- planning set rounds


def test_set_gain_matches_pair_information_and_ignores_settled_orders():
    pair = set_gain(
        np.array([0.3, 0.0]), np.eye(2) * 0.5, np.array([[0, 1]]), "rank", np.ones((1, 2, 2))
    )
    exact = order_information(np.array([0.3]), np.array([1.0]))
    assert pair[0] == pytest.approx(exact[0], rel=0.25)
    one_set, ones = np.array([[0, 1, 2]]), np.ones((1, 3, 3))
    settled = set_gain(np.array([6.0, 3.0, 0.0]), np.eye(3) * 0.01, one_set, "rank", ones)
    unsure = set_gain(np.zeros(3), np.eye(3), one_set, "rank", ones)
    picked = set_gain(np.zeros(3), np.eye(3), one_set, "pick", ones)
    assert settled[0] < 1e-3 and unsure[0] > 0.2
    assert 0 < picked[0] < unsure[0]  # picking the best says less than a full order


@pytest.mark.parametrize("k", [3, 4, 5])
def test_the_information_of_an_ordering_matches_a_plain_sum_over_every_order(k):
    """``_fisher`` lays each stage's choice out by item to stay fast; check it against the
    textbook sum: P(order) times the information of each of its k - 1 choices."""
    import itertools

    mu = np.random.default_rng(k).normal(0, 1.5, (2, k))
    expected = np.zeros((2, k, k))
    for s in range(2):
        for order in itertools.permutations(range(k)):
            p, info = 1.0, np.zeros((k, k))
            for r in range(k - 1):
                rest = list(order[r:])
                q = np.exp(mu[s, rest] - mu[s, rest].max())
                q /= q.sum()
                p *= q[0]
                info[np.ix_(rest, rest)] += np.diag(q) - np.outer(q, q)
            expected[s] += p * info
    np.testing.assert_allclose(_fisher(mu, "rank"), expected, atol=1e-12)


def test_sets_never_hold_a_known_tie():
    theta = np.array([1.0, 1.0, 0.2, 0.0, -0.3, -1.0])
    cov = np.eye(6) * 0.3
    cov[0, 0] = cov[1, 1] = 0.001  # items 0 and 1 are a confident tie
    ranks = [(p, 1, 6) for p in range(6)]
    plan = plan_round("exact", theta, cov, ranks, Timing(), 1, dict.fromkeys(range(6), 5))
    assert any(c.kind != "pair" for c in plan.candidates)
    assert all(not {0, 1} <= set(c.items) for c in plan.candidates if c.kind != "pair")


def test_timing_uses_the_judges_own_set_times_once_there_are_enough():
    guess = Timing.fit([(0.5, 2.0)] * 30)
    assert guess.set_seconds("rank", 4) == pytest.approx(SET_TIME_GUESS[("rank", 4)] * 2.0)
    few = Timing.fit([], [("rank", 4, 20.0)] * (MIN_SET_SAMPLES - 1))
    assert few.set_seconds("rank", 4) == pytest.approx(SET_TIME_GUESS[("rank", 4)] * 3.0)
    enough = Timing.fit([], [("rank", 4, 20.0)] * MIN_SET_SAMPLES + [("pick", 3, 4.0)])
    assert enough.set_seconds("rank", 4) == 20.0
    assert enough.set_seconds("pick", 3) == pytest.approx(SET_TIME_GUESS[("pick", 3)] * 3.0)


# ---------------------------------------------------------------- mixed rounds end to end

ITEMS = [f"item-{k}" for k in range(8)]


def first_set_round(rk, slug, kind=None):
    """Answer pairs ("first shown wins") until the planner asks a pick or rank round."""
    for _ in range(40):
        view = rk.next_round(slug)
        if view.kind != "pair" and kind in (None, view.kind):
            return view
        rk.answer(slug, first_listed(view))
    raise AssertionError(f"no {kind or 'pick or rank'} round in 40 rounds")


def kinds_asked(rk, slug, judge, rounds) -> set[str]:
    kinds = set()
    for _ in range(rounds):
        try:
            view = rk.next_round(slug)
        except NothingToAsk:
            break
        kinds.add(view.kind)
        rk.answer(slug, judge.answer(view.kind, [i.name for i in view.items]))
    return kinds


def test_mixed_lists_ask_picks_and_rankings_and_default_lists_never_do(rk):
    truth = {n: float(k) for k, n in enumerate(ITEMS)}
    rk.create_list("m", "M", ITEMS, seed=1, mode="exact", rounds="mixed")
    rk.create_list("p", "P", ITEMS, seed=1, mode="exact")  # the default
    assert kinds_asked(rk, "m", SimulatedJudge(truth, seed=2), 40) & {"pick", "rank"}
    assert kinds_asked(rk, "p", SimulatedJudge(truth, seed=2), 40) == {"pair"}
    assert rk.verify("m") == []
    with pytest.raises(RankifyError, match="rounds"):
        rk.create_list("bad", "B", ITEMS, rounds="sets")


def test_a_ranking_answer_orders_its_items(rk):
    rk.create_list("r", "R", ITEMS, seed=3, rounds="mixed")
    view = first_set_round(rk, "r", "rank")
    before = {i.name: i.score for i in rk.ranking("r").items}
    numbers = [i.n for i in view.items][::-1]  # the last shown is best
    rk.answer("r", numbers)
    after = {i.name: i.score for i in rk.ranking("r").items}
    moves = [after[view.items[k - 1].name] - before[view.items[k - 1].name] for k in numbers]
    assert moves == sorted(moves, reverse=True)  # the best moved up most, the worst down most


def test_answers_to_picks_and_rankings_are_checked(rk):
    rk.create_list("r", "R", ITEMS, seed=3, rounds="mixed")
    view = first_set_round(rk, "r", "rank")
    k = len(view.items)
    with pytest.raises(RankifyError):
        rk.answer("r", [1])  # a ranking needs every number, or all but the last
    with pytest.raises(RankifyError):
        rk.answer("r", [1, 1, *range(3, k + 1)])
    rk.answer("r", [int("".join(str(x) for x in range(k, 1, -1)))])  # "5432": the 1 is implied
    stored = store.effective_rounds(rk.conn, store.get_list(rk.conn, "r").id)[-1]
    assert stored.answer == [view.items[x - 1].id for x in range(k, 0, -1)]

    rk.create_list("q", "Q", ITEMS, seed=5, rounds="mixed")
    view = first_set_round(rk, "q", "pick")
    with pytest.raises(RankifyError, match="best item"):
        rk.answer("q", [1, 2])
    rk.answer("q", [2])
    stored = store.effective_rounds(rk.conn, store.get_list(rk.conn, "q").id)[-1]
    assert stored.kind == "pick" and stored.answer == [view.items[1].id]


def test_cant_decide_on_a_set_teaches_nothing_and_is_not_asked_again(rk):
    rk.create_list("r", "R", ITEMS, seed=3, rounds="mixed")
    view = first_set_round(rk, "r")
    before = rk.ranking("r")
    rk.answer("r", cant_decide=True)
    after = rk.ranking("r")
    assert after.answers == before.answers
    assert [i.score for i in after.items] == pytest.approx([i.score for i in before.items])
    assert {i.name for i in rk.next_round("r").items} != {i.name for i in view.items}


def test_why_explains_a_set_round(rk):
    rk.create_list("r", "R", ITEMS, seed=3, rounds="mixed")
    view = first_set_round(rk, "r")
    why = rk.why("r", view.round)
    assert why.chosen["kind"] == view.kind
    assert why.chosen["names"] == [i.name for i in view.items]
    assert {"pick 5", "rank 5"} <= set(why.timing["sets"])
