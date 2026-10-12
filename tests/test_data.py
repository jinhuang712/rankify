"""Managing data: export, rebuild, tiers, and calibrating from several lists."""

import json

import numpy as np
from typer.testing import CliRunner

from rankify import store
from rankify.bench import HUMAN, Judge
from rankify.cli.main import app
from rankify.engine.judge import HumanParams, human_answer
from rankify.service import NothingToAsk, RankedItem, Rankify, tiers

from .conftest import SimulatedJudge, run_rounds

NAMES = [f"item-{k}" for k in range(7)]


def _busy_list(rk: Rankify) -> None:
    """A mixed list with every kind of record: sets, a can't-decide, an undo, a removed and
    an added item."""
    rk.create_list("m", "Mixed", NAMES, seed=5, rounds="mixed")
    judge = SimulatedJudge({n: float(k) for k, n in enumerate(reversed([*NAMES, "item-new"]))}, 1)
    run_rounds(rk, "m", judge, 6)
    rk.next_round("m")
    rk.answer("m", cant_decide=True)
    rk.undo("m")
    rk.remove_item("m", "item-3")
    rk.add_item("m", "item-new", note="late")
    run_rounds(rk, "m", judge, 6)


def _replay(records: list[dict], conn) -> None:
    """Load an export into an empty database with the store alone, as an import would."""
    head, items, rounds = records[0], [], []
    for r in records[1:]:
        (items if "item" in r else rounds).append(r)
    list_id = store.insert_list(conn, head["list"], head["title"], head["settings"])
    ids = {}
    for it in items:
        ids[it["item"]] = store.insert_item(conn, list_id, it["name"], it["note"])
        if it["removed_at"]:
            store.mark_removed(conn, ids[it["item"]])
    new_id = {}
    for r in rounds:
        new_id[r["round"]] = store.insert_round(
            conn,
            list_id,
            store.judge_id(conn, r["judge"]),
            query_id=None,
            kind=r["kind"],
            shown=[ids[i] for i in r["shown"]],
            answer=None if r["answer"] is None else [ids[i] for i in r["answer"]],
            outcome=r["outcome"],
            undoes=new_id.get(r["undoes"]),
            ms=r["ms"],
            seed=r["seed"],
            engine_version=r["engine_version"],
        )
    conn.commit()


def test_an_export_holds_the_whole_log_and_replays_to_the_same_ranking(rk, conn, tmp_path):
    _busy_list(rk)
    records = rk.export("m")
    head = records[0]
    assert head["rankify"] == "export" and head["format"] == 1 and head["list"] == "m"
    items = [r for r in records if "item" in r]
    rounds = [r for r in records if "round" in r]
    assert [it["item"] for it in items] == list(range(1, len(NAMES) + 2))
    assert len(rounds) == conn.execute("SELECT COUNT(*) FROM rounds").fetchone()[0]
    assert {r["outcome"] for r in rounds} == {"answered", "cant_decide", "undo"}
    undo = next(r for r in rounds if r["outcome"] == "undo")
    assert rounds[undo["undoes"] - 1]["outcome"] == "cant_decide"
    assert any(r["kind"] != "pair" for r in rounds)
    other = store.connect(tmp_path / "replayed.db")
    _replay(json.loads(json.dumps(records)), other)
    a, b = rk.ranking("m"), Rankify(other).ranking("m")
    assert [i.name for i in a.items] == [i.name for i in b.items]
    np.testing.assert_allclose([i.score for i in a.items], [i.score for i in b.items], atol=1e-6)


def test_export_command_writes_json_lines(tmp_path):
    db = tmp_path / "e.db"
    _busy_list(Rankify(store.connect(db)))
    runner = CliRunner()
    shown = runner.invoke(app, ["--db", str(db), "export", "m"])
    assert shown.exit_code == 0
    lines = [json.loads(line) for line in shown.stdout.splitlines()]
    assert lines[0]["list"] == "m" and any("round" in r for r in lines)
    out = tmp_path / "m.jsonl"
    written = runner.invoke(app, ["--db", str(db), "export", "m", "--out", str(out)])
    assert written.exit_code == 0 and "rounds" in written.stdout
    assert out.read_text(encoding="utf-8") == shown.stdout


def test_rebuild_refits_with_this_engine_and_shows_what_moved(rk, conn):
    _busy_list(rk)
    rk.forecast("m", budget_ms=100)
    assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 1
    fit = store.latest_fit(conn, store.get_list(conn, "m").id)
    top, second = fit.items[0], fit.items[1]
    with store.Transaction(conn):  # as if an older engine had ranked the top two the other way
        conn.execute("UPDATE fits SET engine_version = '0.0.1' WHERE id = ?", (fit.id,))
        for item, rank in ((top, second.rank), (second, top.rank)):
            conn.execute(
                "UPDATE fit_items SET rank = ? WHERE fit_id = ? AND item_id = ?",
                (rank, fit.id, item.item_id),
            )
    view = rk.rebuild("m")
    assert view.engine_before == "0.0.1" and view.forecasts_dropped == 1
    assert len(view.moved) == 2
    assert conn.execute("SELECT COUNT(*) FROM forecasts").fetchone()[0] == 0
    assert rk.verify("m") == []
    again = rk.rebuild("m")
    assert again.moved == [] and again.forecasts_dropped == 0


def test_tiers_break_where_the_order_is_confident():
    def item(rank, conf):
        return RankedItem(rank, rank, f"i{rank}", 0.0, conf, (rank, rank))

    groups = tiers([item(1, 0.95), item(2, 0.5), item(3, 0.92), item(4, None)])
    assert [[i.rank for i in g] for g in groups] == [[1], [2, 3], [4]]
    assert tiers([item(1, None), item(2, None)]) is None  # Elo and the sorts have no Confidence


def test_show_tiers_prints_and_tags_tiers(tmp_path):
    db = tmp_path / "t.db"
    rk = Rankify(store.connect(db))
    rk.create_list("t", "Tiers", NAMES, seed=2)
    run_rounds(rk, "t", SimulatedJudge({n: 3.0 * k for k, n in enumerate(NAMES)}, 2), 40)
    runner = CliRunner()
    text = runner.invoke(app, ["--db", str(db), "show", "t", "--tiers"])
    assert text.exit_code == 0 and "Tier 1" in text.stdout
    data = json.loads(
        runner.invoke(app, ["--db", str(db), "show", "t", "--tiers", "--json"]).stdout
    )
    tier_numbers = [i["tier"] for i in data["items"]]
    assert tier_numbers[0] == 1 and tier_numbers == sorted(tier_numbers)
    assert (
        "tier"
        not in json.loads(runner.invoke(app, ["--db", str(db), "show", "t", "--json"]).stdout)[
            "items"
        ][0]
    )


def test_calibrate_measures_how_long_picks_and_orderings_take(rk):
    """Pairs from a calibration list, sets from a mixed list, by a judge whose picks and
    orderings take twice the benchmark's guess. Over seeds the estimate runs about 10% low
    (the fitted gaps are noisy), but it tells half, guessed and double time apart."""
    rng = np.random.default_rng(8)
    names = [f"item-{k:02d}" for k in range(10)]
    theta = dict(zip(names, 1.5 * rng.standard_t(3, 10), strict=True))
    rk.create_list("cal", "Cal", names, seed=8, calibrate=True)
    for t in range(60):
        view = rk.next_round("cal")
        first, second = (i.name for i in view.items)
        pick, secs = human_answer(HUMAN, rng, theta[first] - theta[second], t)
        if pick is None:
            rk.answer("cal", cant_decide=True, ms=int(secs * 1000))
        else:
            rk.answer("cal", [pick], ms=int(secs * 1000))
    rk.create_list("mix", "Mix", names, seed=8, rounds="mixed")
    judge = Judge(theta, "human", np.random.default_rng(9), HumanParams(set_time_scale=2.0))
    for t in range(40):
        try:
            view = rk.next_round("mix")
        except NothingToAsk:
            break
        shown = [i.name for i in view.items]
        if view.kind == "pair":
            pick, secs = judge.answer(shown, t)
            numbers = None if pick is None else [pick]
        else:
            numbers, secs = judge.answer_set(shown, view.kind, t)
        if numbers is None:
            rk.answer("mix", cant_decide=True, ms=int(secs * 1000))
        else:
            rk.answer("mix", numbers, ms=int(secs * 1000))
    profile = rk.calibrate(["cal", "mix"])
    assert "set_time_scale" in profile.measured and profile.set_answers >= 8
    assert 1.4 < profile.set_time_scale < 2.9
    assert profile.set_seconds and any("planner" in n for n in profile.notes)
    only_pairs = rk.calibrate("cal")
    assert "set_time_scale" not in only_pairs.measured and only_pairs.set_answers == 0
