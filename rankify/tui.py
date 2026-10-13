"""The terminal UI for answering rounds (`rankify play`), built with Textual.

One round at a time. Type the numbers: one for a pair or a pick, all but the last for an
ordering (which can also be arranged with the arrow keys and Space). `t` is "can't decide",
`u` undoes, `r` shows the ranking, `q` quits. Rounds left are worked out just after each
round is drawn, so the round never waits for them.
"""

import asyncio
from time import perf_counter
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Static

from rankify.engine.forecast import forecast_rounds
from rankify.service import NothingToAsk, Rankify, RankifyError, RoundView


class PlayApp(App):
    """Answer rounds of one list until its mode's target, a round limit, or `q`."""

    CSS = """
    Screen { padding: 1 2; }
    #top { color: $text-muted; }
    #prompt { margin-top: 1; text-style: bold; }
    #items { margin-top: 1; }
    #typed { margin-top: 1; color: $accent; }
    #note { color: $text-muted; }
    #ranking { margin-top: 1; height: auto; max-height: 24; }
    """
    BINDINGS: ClassVar = [
        Binding("t", "cant_decide", "can't decide"),
        Binding("u", "undo", "undo"),
        Binding("r", "ranking", "ranking"),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self, rk: Rankify, slug: str, mode: str | None = None, rounds: int | None = None):
        super().__init__()
        self.rk, self.slug, self.mode, self.limit = rk, slug, mode, rounds
        self.view: RoundView | None = None
        self.typed: list[int] = []  # numbers typed so far, best first
        self.order: list[int] = []  # an ordering's items as arranged with the arrow keys
        self.cursor = 0
        self.holding = False  # Space picked up the item under the cursor
        self.shown_at = 0.0
        self.answered = 0
        self.done = False
        self.forecast_text = ""  # the last finished estimate
        self.left = "rounds left: …"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(id="top")
            yield Static(id="prompt")
            yield Static(id="items")
            yield Static(id="typed")
            yield Static(id="note")
            yield DataTable(id="ranking", show_cursor=False)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#ranking", DataTable)
        table.add_columns("#", "Item", "Score", "Confidence", "Could be")
        table.can_focus = False  # the arrow keys arrange an ordering, not scroll the table
        table.display = False
        self.next_round()

    # ------------------------------------------------------------ rounds

    def next_round(self) -> None:
        if self.limit is not None and self.answered >= self.limit:
            self.finish(f"{self.answered} answers this session.")
            return
        try:
            self.view = self.rk.next_round(self.slug, mode=self.mode)
        except NothingToAsk as e:
            self.finish(str(e).split(": ", 1)[-1].capitalize() + ".")
            return
        except RankifyError as e:  # for example, fewer than 2 items left
            self.finish(str(e).capitalize() + ".")
            return
        view = self.view
        self.typed, self.cursor, self.holding = [], 0, False
        self.order = [i.n for i in view.items]
        self.shown_at = perf_counter()
        # Keep showing the last estimate until the new one is ready.
        self.left = f"{self.forecast_text}, updating" if self.forecast_text else "rounds left: …"
        self.refresh_forecast(view.round)
        self.draw()

    def finish(self, why: str) -> None:
        self.done, self.view = True, None
        self.left = "finished"
        self.query_one("#prompt", Static).update(f"Done. {why}")
        self.query_one("#items", Static).update("")
        self.query_one("#typed", Static).update("")
        self.query_one("#note", Static).update("Press q to leave.")
        self.show_ranking(True)
        self.draw_top()

    def submit(self, numbers: list[int] | None) -> None:
        if self.view is None:
            return
        ms = int((perf_counter() - self.shown_at) * 1000)
        try:
            self.rk.answer(
                self.slug, numbers, cant_decide=numbers is None, round_seq=self.view.round, ms=ms
            )
        except RankifyError as e:
            self.typed = []
            self.query_one("#note", Static).update(str(e))
            return
        self.answered += 1
        self.next_round()
        self.refresh_ranking()

    # ------------------------------------------------------------ keys

    def on_key(self, event) -> None:
        view = self.view
        if view is None:
            return
        k = len(view.items)
        if event.character and event.character.isdigit():
            n = int(event.character)
            if 1 <= n <= k and n not in self.typed:
                self.typed.append(n)
                need = k - 1 if view.kind == "rank" else 1
                if len(self.typed) >= need:
                    self.submit(self.typed if view.kind == "rank" else self.typed[:1])
                    return
            event.stop()
        elif event.key == "backspace" and self.typed:
            self.typed.pop()
        elif view.kind == "rank" and event.key in ("up", "down"):
            step = -1 if event.key == "up" else 1
            target = self.cursor + step
            if 0 <= target < k:
                if self.holding:
                    self.order[self.cursor], self.order[target] = (
                        self.order[target],
                        self.order[self.cursor],
                    )
                self.cursor = target
        elif view.kind == "rank" and event.key == "space":
            self.holding = not self.holding
        elif view.kind == "rank" and event.key == "enter" and not self.typed:
            self.submit(self.order)
            return
        else:
            return
        self.draw()

    def action_cant_decide(self) -> None:
        if self.view is not None:
            self.submit(None)

    def action_undo(self) -> None:
        try:
            self.rk.undo(self.slug)
        except RankifyError as e:
            self.query_one("#note", Static).update(str(e))
            return
        self.answered = max(0, self.answered - 1)
        self.done = False
        self.next_round()
        self.refresh_ranking()
        self.query_one("#note", Static).update("Undone. Asking it again.")

    def action_ranking(self) -> None:
        table = self.query_one("#ranking", DataTable)
        self.show_ranking(not table.display)

    # ------------------------------------------------------------ drawing

    def draw_top(self) -> None:
        lst = self.rk.ranking(self.slug)
        mode = (self.mode or lst.mode).capitalize()
        count = f"{self.answered} answered" if self.answered else "no answers yet this session"
        self.query_one("#top", Static).update(f"{lst.title} · {mode} · {self.left} · {count}")

    def draw(self) -> None:
        view = self.view
        if view is None:
            return
        self.draw_top()
        self.query_one("#prompt", Static).update(f"Round {view.round} · {view.prompt}")
        names = {i.n: i.name for i in view.items}
        if view.kind == "rank":
            lines = []
            for place, n in enumerate(self.order):
                mark = ">" if place == self.cursor else " "
                held = " (moving)" if self.holding and place == self.cursor else ""
                lines.append(f" {mark} {n}  {names[n]}{held}")
            hint = "Type the numbers best first, or arrange with ↑ ↓ and Space, then Enter."
        else:
            lines = [f"   {n}  {name}" for n, name in names.items()]
            hint = "Press the number of the " + ("better" if view.kind == "pair" else "best")
            hint += " one."
        self.query_one("#items", Static).update("\n".join(lines))
        typed = " ".join(map(str, self.typed))
        self.query_one("#typed", Static).update(f"> {typed}" if typed else "> ")
        self.query_one("#note", Static).update(hint)

    def show_ranking(self, visible: bool) -> None:
        table = self.query_one("#ranking", DataTable)
        table.display = visible
        if visible:
            self.refresh_ranking()

    def refresh_ranking(self) -> None:
        table = self.query_one("#ranking", DataTable)
        if not table.display:
            return
        table.clear()
        for i in self.rk.ranking(self.slug).items:
            score = "" if i.score is None else f"{i.score:.0f}"
            conf = "" if i.confidence is None else f"{i.confidence:.0%}"
            could = "" if i.could_be is None else f"#{i.could_be[0]}–#{i.could_be[1]}"
            table.add_row(str(i.rank), i.name, score, conf, could)

    # ------------------------------------------------------------ forecast

    def refresh_forecast(self, round_no: int) -> None:
        """Start forecasting from the numbers as they are now. A newer round cancels it."""
        args = self.rk.forecast_inputs(self.slug, self.mode)
        if args is None:
            self.left = "rounds left: not forecast for this list"
            return
        self.forecast_worker(round_no, args)

    @work(exclusive=True, group="forecast")
    async def forecast_worker(self, round_no: int, args: dict) -> None:
        await asyncio.sleep(0)  # let the round show first; the forecast takes milliseconds
        self.show_forecast(round_no, forecast_rounds(**args))

    def show_forecast(self, round_no: int, f) -> None:
        if self.view is None or self.view.round != round_no:
            return
        if f.median is None:
            self.forecast_text = f"at least {f.at_least} rounds left"
        elif f.high is None:
            self.forecast_text = f"~{f.median} rounds left ({f.low}+)"
        else:
            self.forecast_text = f"~{f.median} rounds left ({f.low}–{f.high})"
        self.left = self.forecast_text
        self.draw_top()


def run(rk: Rankify, slug: str, mode: str | None = None, rounds: int | None = None) -> int:
    """Run the UI; returns the number of answers given."""
    app = PlayApp(rk, slug, mode, rounds)
    app.run()
    return app.answered
