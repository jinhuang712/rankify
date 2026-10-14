"""The agent report, and JSON output from every command that prints results (goal G11)."""

import json

import pytest
from typer.testing import CliRunner

from rankify.cli.main import app
from rankify.report import build, markdown
from rankify.service import Rankify

from .conftest import SimulatedJudge, run_rounds

NAMES = ["Kyoto", "Lisbon", "Reykjavik", "Cape Town", "Buenos Aires", "Hanoi"]
TRUTH = {n: 3.0 - k for k, n in enumerate(NAMES)}  # far apart: answers are predictable


def test_report_finds_upsets_slow_answers_and_the_judges_habits(rk):
    # A calibration list asks random pairs, so the best and the worst item do meet.
    rk.create_list("t", "Trips", NAMES, seed=3, calibrate=True)
    flipped = False
    for _ in range(80):
        shown = [i.name for i in rk.next_round("t").items]
        better = max(shown, key=lambda x: TRUTH[x])
        if set(shown) == {"Kyoto", "Hanoi"} and not flipped:  # one answer against the grain
            rk.answer("t", [shown.index("Hanoi") + 1], ms=20000)
            flipped = True
        else:
            rk.answer("t", [shown.index(better) + 1], ms=2000)
    assert flipped
    data = build(rk, "t")
    assert data["ranking"][0]["name"] == "Kyoto"
    assert any(u["winner"] == "Hanoi" and u["loser"] == "Kyoto" for u in data["upsets"])
    assert any(s["seconds"] == 20.0 for s in data["slow"])
    j = data["judge"]
    assert 0.5 < j["agreement"] <= 1 and j["statements"] >= 40
    text = markdown(data)
    for heading in ("## Ranking", "## Weak spots", "## Slow decisions", "## The judge"):
        assert heading in text
    assert "Hanoi beat Kyoto" in text


def test_judges_who_disagree_are_shown(conn):
    a, b = Rankify(conn, judge="ana"), Rankify(conn, judge="ben")
    a.create_list("p", "P", ["x", "y"], seed=1)
    for _ in range(1):  # a judge is asked a pair once, unless their other answers contradict it
        view = a.next_round("p")
        a.answer("p", [[i.name for i in view.items].index("x") + 1])
        view = b.next_round("p")
        b.answer("p", [[i.name for i in view.items].index("y") + 1])
    data = build(a, "p")
    assert {j["judge"] for j in data["judges"]} == {"ana", "ben"}
    split = data["disagreements"][0]
    assert split["items"] == ["x", "y"]
    assert split["for_first"] == ["ana"] and split["for_second"] == ["ben"]
    assert "Split on x vs y" in markdown(data)


def test_slow_means_slow_for_that_kind_and_size_of_round():
    """An ordering of five takes longer than a pair; only a slow one of its own kind counts."""
    from types import SimpleNamespace

    from rankify.report import _slow

    def rnd(i, kind, shown, ms):
        return SimpleNamespace(query_id=i, judge_id=1, kind=kind, shown=shown, answer=shown, ms=ms)

    rounds = [rnd(i, "pair", [1, 2], 2000) for i in range(6)]
    rounds += [rnd(10 + i, "rank", [1, 2, 3, 4, 5], 9000) for i in range(6)]
    rounds += [rnd(20, "rank", [1, 2, 3, 4, 5], 25000), rnd(21, "pair", [1, 2], 2500)]
    slow = _slow(rounds, {i: i for i in range(30)}, {k: str(k) for k in range(6)},
                 {k: k for k in range(6)})  # fmt: skip
    assert [s["round"] for s in slow] == [20]
    assert slow[0]["usual_seconds"] == 9.0


def test_report_works_for_methods_without_scores(rk):
    rk.create_list("e", "E", NAMES, method="elo", seed=2)
    run_rounds(rk, "e", SimulatedJudge(TRUTH, seed=4), 10)
    data = build(rk, "e")
    assert data["method"] == "elo" and data["rounds_left"] is None
    assert data["upsets"] == [] and data["judge"] == {}
    assert "## Ranking" in markdown(data)


def test_report_command_prints_markdown_or_json(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "r.db")
    items = tmp_path / "items.txt"
    items.write_text("\n".join(NAMES), encoding="utf-8")
    runner.invoke(app, ["--db", db, "new", "r", "R", "--items", str(items), "--seed", "1"])
    md = runner.invoke(app, ["--db", db, "report", "r"])
    assert md.exit_code == 0, md.output
    assert md.output.startswith("# Ranking report: R")
    data = json.loads(runner.invoke(app, ["--db", db, "report", "r", "--format", "json"]).output)
    assert set(data) >= {"ranking", "ties", "weak_spots", "slow", "upsets", "judge", "judges"}
    assert runner.invoke(app, ["--db", db, "report", "r", "--format", "pdf"]).exit_code == 1


# Commands that print results. `play` is interactive and `bench` writes a Markdown report.
RESULT_COMMANDS = (
    "new", "add", "remove", "lists", "next", "answer", "undo", "show", "verify", "why",
    "report", "forecast", "calibrate", "rebuild",
)  # fmt: skip


@pytest.mark.parametrize("command", RESULT_COMMANDS)
def test_every_result_command_has_json(command):
    result = CliRunner().invoke(app, [command, "--help"], terminal_width=200)
    assert result.exit_code == 0
    assert "--json" in result.output
