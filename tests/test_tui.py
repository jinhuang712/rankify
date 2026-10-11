"""The terminal UI, driven by Textual's test pilot."""

import asyncio

from textual.widgets import DataTable, Static

from rankify import store
from rankify.tui import PlayApp

from .conftest import first_listed

ITEMS = [f"item-{k}" for k in range(8)]


def drive(app: PlayApp, keys: list[str], wait_for_forecast: bool = False) -> dict:
    """Press ``keys`` in a headless app; return what the screen shows at the end."""
    shown: dict = {}

    async def go() -> None:
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
            if wait_for_forecast:
                await app.workers.wait_for_complete()
                await pilot.pause()
            for name in ("top", "prompt", "items", "typed", "note"):
                shown[name] = str(app.query_one(f"#{name}", Static).render())
            shown["table"] = app.query_one("#ranking", DataTable).display

    asyncio.run(go())
    return shown


def answers(rk, slug) -> int:
    return rk.ranking(slug).answers


def test_answer_undo_cant_decide_and_ranking_view(rk):
    rk.create_list("p", "Pets", ITEMS, seed=1)
    app = PlayApp(rk, "p")
    screen = drive(app, ["1", "2", "1", "u", "t", "r"])
    assert app.answered == 3  # 1, 2 and "can't decide"; u took the third 1 back
    assert answers(rk, "p") == 3
    assert screen["table"] is True  # r shows the ranking
    assert "Pets" in screen["top"] and "Round" in screen["prompt"]


def test_an_ordering_can_be_arranged_with_arrows_and_space(rk):
    rk.create_list("r", "R", ITEMS, seed=3, mode="exact", rounds="mixed")
    for _ in range(40):  # answer until the planner asks for an ordering
        view = rk.next_round("r")
        if view.kind == "rank":
            break
        rk.answer("r", first_listed(view))
    shown = [i.id for i in view.items]
    app = PlayApp(rk, "r", rounds=1)
    drive(app, ["space", "down", "space", "enter"])  # move the first item down one place
    last = store.effective_rounds(rk.conn, store.get_list(rk.conn, "r").id)[-1]
    assert last.kind == "rank"
    assert last.answer == [shown[1], shown[0], *shown[2:]]


def test_an_ordering_can_be_typed(rk):
    rk.create_list("r", "R", ITEMS, seed=3, mode="exact", rounds="mixed")
    for _ in range(40):
        view = rk.next_round("r")
        if view.kind == "rank":
            break
        rk.answer("r", first_listed(view))
    k = len(view.items)
    app = PlayApp(rk, "r", rounds=1)
    drive(app, [str(n) for n in range(k, 1, -1)])  # last shown is best; the 1 is implied
    last = store.effective_rounds(rk.conn, store.get_list(rk.conn, "r").id)[-1]
    assert last.answer == [i.id for i in reversed(view.items)]


def test_rounds_left_arrive_without_holding_up_the_round(rk):
    rk.create_list("f", "F", ITEMS[:5], seed=2, mode="quick")
    screen = drive(PlayApp(rk, "f"), [], wait_for_forecast=True)
    assert "rounds left" in screen["top"] and "…" not in screen["top"]


def test_a_list_too_short_to_rank_ends_the_session_instead_of_crashing(rk):
    rk.create_list("one", "One", ["only"], seed=1)
    app = PlayApp(rk, "one")
    screen = drive(app, [])
    assert app.done and "at least 2 items" in screen["prompt"]


def test_the_session_ends_when_the_target_is_reached(rk):
    rk.create_list("d", "D", ["best", "worst"], seed=1, mode="quick")
    app = PlayApp(rk, "d")

    async def go() -> str:
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause()
            for _ in range(40):
                if app.done:
                    break
                names = [i.name for i in app.view.items]
                await pilot.press(str(names.index("best") + 1))
                await pilot.pause()
            return str(app.query_one("#prompt", Static).render())

    prompt = asyncio.run(go())
    assert app.done and prompt.startswith("Done.")
