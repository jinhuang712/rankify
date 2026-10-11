"""Speed targets from DESIGN.md, for lists of 200 items. Times are medians of repeated runs."""

import statistics
import time

import numpy as np
import pytest

from rankify import store
from rankify.engine.fit import fit_pairs
from rankify.engine.model import Pairs
from rankify.engine.stats import summarize
from rankify.service import Rankify

pytestmark = pytest.mark.perf

N_ITEMS = 200
N_ANSWERS = 2000


def median_ms(fn, repeat=15):
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times)


@pytest.fixture(scope="module")
def big_pairs():
    rng = np.random.default_rng(0)
    theta = rng.normal(0, 1.5, N_ITEMS)
    a = rng.integers(0, N_ITEMS, N_ANSWERS)
    b = (a + rng.integers(1, N_ITEMS, N_ANSWERS)) % N_ITEMS
    p = 1 / (1 + np.exp(-(theta[a] - theta[b])))
    y = (rng.random(N_ANSWERS) > p).astype(int)
    return Pairs.of(a, b, y)


def test_warm_refit_under_10ms(big_pairs):
    previous = fit_pairs(N_ITEMS, Pairs.of(big_pairs.a[:-1], big_pairs.b[:-1], big_pairs.y[:-1]))
    ms = median_ms(lambda: fit_pairs(N_ITEMS, big_pairs, x0=previous.x))
    print(f"warm refit, {N_ITEMS} items, {N_ANSWERS} answers: {ms:.2f} ms")
    assert ms < 10


def test_summary_time(big_pairs):
    fit = fit_pairs(N_ITEMS, big_pairs)
    ms = median_ms(lambda: summarize(fit.theta, fit.theta_cov, np.arange(N_ITEMS), seed=1))
    print(f"summary (Score, Confidence, Could be), {N_ITEMS} items: {ms:.2f} ms")
    assert ms < 30


def test_answer_to_next_round_under_50ms(tmp_path):
    rng = np.random.default_rng(1)
    names = [f"item-{k:03d}" for k in range(N_ITEMS)]
    truth = dict(zip(names, rng.normal(0, 1.5, N_ITEMS), strict=True))
    rk = Rankify(store.connect(tmp_path / "perf.db"))
    rk.create_list("big", "Big", names, seed=1, mode="exact", rounds="mixed")  # the slower kind

    def pick(view) -> list[int]:  # a judge with real preferences, so the planner keeps asking
        noisy = np.array([truth[i.name] for i in view.items]) + rng.gumbel(size=len(view.items))
        order = [int(k) + 1 for k in np.argsort(-noisy)]
        return order if view.kind == "rank" else order[:1]

    for _ in range(300):
        view = rk.next_round("big")
        rk.answer("big", pick(view))

    save_times, total_times = [], []
    for _ in range(15):
        view = rk.next_round("big")
        t0 = time.perf_counter()
        rk.answer("big", pick(view), round_seq=view.round)
        rk.next_round("big")
        total_times.append((time.perf_counter() - t0) * 1000)
    conn = store.connect(tmp_path / "save.db")
    list_id = store.insert_list(conn, "s", "S", {})
    judge = store.judge_id(conn, "me")
    for k in range(15):
        t0 = time.perf_counter()
        with store.Transaction(conn):
            store.insert_round(
                conn,
                list_id,
                judge,
                query_id=None,
                kind="pair",
                shown=[1, 2],
                answer=[1, 2],
                outcome="answered",
                undoes=None,
                ms=1,
                seed=k,
                engine_version="t",
            )
        save_times.append((time.perf_counter() - t0) * 1000)
    save, total = statistics.median(save_times), statistics.median(total_times)
    p95 = sorted(total_times)[int(0.95 * (len(total_times) - 1))]
    print(
        f"save answer: {save:.2f} ms; answer -> next round: median {total:.1f} ms, p95 {p95:.1f} ms"
    )
    assert save < 5
    assert p95 < 50


def test_terminal_ui_shows_the_next_round_without_a_visible_wait():
    """In `rankify play` on 20 items, from an answer key to the next round drawn, while
    rounds-left forecasts run between keypresses."""
    import asyncio

    from rankify.tui import PlayApp

    rng = np.random.default_rng(3)
    names = [f"item-{k:02d}" for k in range(20)]
    truth = dict(zip(names, rng.normal(0, 1.5, 20), strict=True))
    rk = Rankify(store.connect(":memory:"))
    rk.create_list("t", "T", names, seed=3, mode="stable")
    app = PlayApp(rk, "t", rounds=12)
    times = []
    submit = app.submit

    def timed(numbers):
        t0 = time.perf_counter()
        submit(numbers)
        times.append((time.perf_counter() - t0) * 1000)

    app.submit = timed

    async def go() -> None:
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            while not app.done:
                a, b = (truth[i.name] for i in app.view.items)
                await pilot.press("1" if a > b else "2")

    asyncio.run(go())
    p95 = sorted(times)[int(0.95 * (len(times) - 1))]
    print(f"terminal UI, answer -> next round drawn: median {statistics.median(times):.1f} ms, "
          f"p95 {p95:.1f} ms")  # fmt: skip
    assert len(times) == 12 and p95 < 50
