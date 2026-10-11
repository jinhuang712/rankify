import json

from typer.testing import CliRunner

from rankify.cli.main import app

runner = CliRunner()


def call(db, *args):
    return runner.invoke(app, ["--db", str(db), *args])


def test_full_session_through_the_cli(tmp_path):
    db = tmp_path / "cli.db"
    items = tmp_path / "items.txt"
    items.write_text("Kyoto\nLisbon\n\nReykjavik\n", encoding="utf-8")

    result = call(db, "new", "travel", "Places I want to go", "--items", str(items), "--seed", "3")
    assert result.exit_code == 0, result.output
    assert "3 items" in result.output

    result = call(db, "next", "travel", "--json")
    assert result.exit_code == 0, result.output
    round_ = json.loads(result.output)
    assert round_["kind"] == "pair"
    assert [i["n"] for i in round_["items"]] == [1, 2]
    assert round_["rounds_left"] is None

    result = call(db, "answer", "travel", "2", "--round", str(round_["round"]))
    assert result.exit_code == 0, result.output

    result = call(db, "show", "travel", "--json")
    ranking = json.loads(result.output)
    assert ranking["answers"] == 1
    assert ranking["items"][0]["name"] == round_["items"][1]["name"]
    assert set(ranking["items"][0]) == {"rank", "id", "name", "score", "confidence", "could_be"}

    result = call(db, "show", "travel")
    assert (
        "Score" in result.output and "Confidence" in result.output and "Could be" in result.output
    )

    assert call(db, "verify", "travel").exit_code == 0
    assert "travel" in call(db, "lists").output


def test_errors_exit_with_code_1(tmp_path):
    db = tmp_path / "cli.db"
    result = call(db, "show", "missing")
    assert result.exit_code == 1
    assert "no list named 'missing'" in result.output

    call(db, "new", "one", "One item")
    call(db, "add", "one", "Only")
    result = call(db, "next", "one")
    assert result.exit_code == 1
    assert "at least 2 items" in result.output


def test_undo_and_cant_decide(tmp_path):
    db = tmp_path / "cli.db"
    call(db, "new", "pets", "Pets", "--seed", "1")
    for name in ("Cat", "Dog", "Fish"):
        call(db, "add", "pets", name)
    call(db, "next", "pets")
    assert call(db, "answer", "pets", "--cant-decide").exit_code == 0
    result = call(db, "undo", "pets")
    assert result.exit_code == 0, result.output
    assert "Asking it again" in result.output
    assert json.loads(call(db, "show", "pets", "--json").output)["answers"] == 0


def test_db_can_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("RANKIFY_DB", str(tmp_path / "env.db"))
    result = runner.invoke(app, ["new", "x", "X"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "env.db").exists()
