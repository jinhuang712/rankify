import json
from collections import Counter

import numpy as np
from typer.testing import CliRunner

from rankify import store
from rankify.bench import HUMAN, load_profile, run_one
from rankify.cli.main import app
from rankify.engine.calibration import estimate_profile, simulate_session
from rankify.engine.judge import HumanParams, human_answer
from rankify.service import Rankify


def test_long_session_recovers_the_measurable_settings():
    truth = HumanParams()
    a, b, y, secs = simulate_session(15, 400, truth, 1.5, np.random.default_rng(1))
    p = estimate_profile(15, a, b, y, secs, bootstrap=10)
    assert 1.7 < p.base_seconds < 2.4
    assert 0.08 < p.tie_peak < 0.6
    assert 0.5 < p.score_spread < 4.0
    assert {"close_width", "fatigue", "tie_width"} <= set(p.measured)
    assert "lapse" not in p.measured and "first_bonus" not in p.measured


def test_short_session_only_uses_what_it_can_measure():
    a, b, y, secs = simulate_session(15, 100, HumanParams(), 1.5, np.random.default_rng(2))
    p = estimate_profile(15, a, b, y, secs, bootstrap=5)
    assert "base_seconds" in p.measured and "close_width" not in p.measured
    params = p.judge_params()
    assert params.close_width == HumanParams().close_width  # kept the guess
    assert params.base_seconds == p.base_seconds  # measured
    assert any("keep the default guess" in note for note in p.notes)


def test_calibration_lists_repeat_earlier_pairs_with_sides_swapped(conn):
    rk = Rankify(conn)
    names = [f"item-{k:02d}" for k in range(12)]
    rk.create_list("c", "C", names, seed=3, calibrate=True)
    shown = []
    for _ in range(120):
        view = rk.next_round("c")
        shown.append(tuple(i.name for i in view.items))
        rk.answer("c", [1])
    counts = Counter(frozenset(p) for p in shown)
    repeats = [p for p, c in counts.items() if c >= 2]
    assert len(repeats) >= 8
    # A planned repeat swaps the sides and never repeats one of the last 8 pairs.
    swapped = [k for k, pair in enumerate(shown) if pair[::-1] in shown[: max(0, k - 8)]]
    assert swapped


def test_play_answers_with_single_keys(tmp_path):
    runner = CliRunner()
    db = str(tmp_path / "p.db")
    items = tmp_path / "items.txt"
    items.write_text("A\nB\nC\nD\n", encoding="utf-8")
    runner.invoke(app, ["--db", db, "new", "p", "P", "--items", str(items), "--seed", "1"])
    result = runner.invoke(app, ["--db", db, "play", "p"], input="x1\n2tuq")
    assert result.exit_code == 0, result.output
    assert "can't decide" in result.output and "undone" in result.output
    ranking = json.loads(runner.invoke(app, ["--db", db, "show", "p", "--json"]).stdout)
    assert ranking["answers"] == 2  # 1, 2 and t answered; u took the "t" back


def test_calibrate_command_writes_a_profile_the_benchmark_reads(tmp_path):
    db = tmp_path / "c.db"
    rk = Rankify(store.connect(db))
    names = [f"item-{k:02d}" for k in range(10)]
    rk.create_list("cal", "Cal", names, seed=4, calibrate=True)
    rng = np.random.default_rng(4)
    theta = dict(zip(names, 1.5 * rng.standard_t(3, 10), strict=True))
    for t in range(80):
        view = rk.next_round("cal")
        first, second = (i.name for i in view.items)
        pick, secs = human_answer(HUMAN, rng, theta[first] - theta[second], t)
        if pick is None:
            rk.answer("cal", cant_decide=True, ms=int(secs * 1000))
        else:
            rk.answer("cal", [pick], ms=int(secs * 1000))
    out = tmp_path / "judge.json"
    result = CliRunner().invoke(app, ["--db", str(db), "calibrate", "cal", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "measured" in result.output and "keeps the guess" in result.output
    profile = load_profile(out)
    assert "base_seconds" in profile["params"]
    assert "lapse" not in profile["params"]
    res = run_one("rankify", "human", 6, seed=1, budget=20, profile=profile)
    assert res.rounds == 20
