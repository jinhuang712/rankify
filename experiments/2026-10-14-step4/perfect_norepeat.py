"""The failing test's setting (perfect judge, 10 items, seeds as in the test), old and new
formula, with no repeats: why the session stopped, whether rankify thinks the target holds,
whether it really does, and rounds. usage: perfect_norepeat.py <worktree>"""

import sys

sys.path.insert(0, sys.argv[1])

import numpy as np  # noqa: E402

import rankify.engine.planner as planner  # noqa: E402
import rankify.service as service  # noqa: E402

planner.ASK_AGAIN = "contradicted"  # the rule as first tried (the default is "always")
from rankify import store  # noqa: E402
from rankify.bench import Judge, hidden_scores, targets_met  # noqa: E402
from rankify.service import NothingToAsk, Rankify  # noqa: E402


def answer_as(judge, rk, slug, view, t):
    names = [i.name for i in view.items]
    pick, secs = judge.answer(names, t)
    rk.answer(slug, None if pick is None else [pick], cant_decide=pick is None, ms=int(secs * 1000))


for ep in (False, True):
    service.EP_FIT = ep
    for mode in ("quick", "stable", "exact"):
        rng = np.random.default_rng(3)
        names = [f"item-{k:02d}" for k in range(10)]
        theta = hidden_scores(names, rng, 3.0)
        judge = Judge(theta, "perfect", np.random.default_rng(4))
        rk = Rankify(store.connect(":memory:"))
        rk.create_list("p", "P", names, seed=2, mode=mode)
        why, t = "budget", 0
        for t in range(300):
            try:
                view = rk.next_round("p")
            except NothingToAsk as e:
                why = str(e).split(": ")[-1]
                break
            answer_as(judge, rk, "p", view, t)
        ranking = rk.ranking("p")
        right = targets_met([i.name for i in ranking.items], theta)[mode]
        print(
            f"{'new' if ep else 'old'} formula, {mode:6s}: stopped by '{why}' after {t} rounds; "
            f"rankify thinks target holds: {ranking.target_reached}; really right: {right}"
        )
