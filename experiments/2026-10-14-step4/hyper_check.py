"""Is it the firm starting belief (hyperprior) that holds the learned spread down? Run sessions
to their stop, then refit the same answers with the hyperprior as shipped (1.5, sd 0.75) and
with a nearly flat one (sd 10), and compare the learned spread with the true one.
usage: hyper_check.py <worktree> <judges> <n> <mode> <runs>"""

import math
import os
import statistics
import sys

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])
os.nice(10)

import numpy as np  # noqa: E402

from rankify import store  # noqa: E402
from rankify.bench import HUMAN, MODEL_SLOPE, Judge, hidden_scores  # noqa: E402
from rankify.engine.fit import SigmaPrior, fit_pairs_learning_sigma  # noqa: E402
from rankify.engine.model import Choices, Pairs, Prior  # noqa: E402
from rankify.service import NothingToAsk, Rankify  # noqa: E402

HYPERS = {"shipped": SigmaPrior(1.5, 0.75), "flat": SigmaPrior(1.5, 10.0)}

judges, n, mode, runs = sys.argv[2].split(","), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
for kind in judges:
    if kind in ("human", "noisy"):
        slope = 1.702 / (math.sqrt(2.0) * HUMAN.noise)
    else:
        slope = MODEL_SLOPE.get(kind, MODEL_SLOPE["normal"])
    out = {h: [] for h in HYPERS}
    true_sd, answers = [], []
    for r in range(runs):
        seed = 70000 + 1000 * n + r
        rng = np.random.default_rng(seed)
        names = [f"item-{k:02d}" for k in range(n)]
        theta = hidden_scores(names, rng, 1.5)
        judge = Judge(theta, kind, np.random.default_rng([seed, 1]))
        rk = Rankify(store.connect(":memory:"))
        rk.create_list("t", "T", names, mode=mode, seed=seed)
        for effort in range(20 * n):
            try:
                view = rk.next_round("t")
            except NothingToAsk:
                break
            pick, secs = judge.answer([i.name for i in view.items], effort)
            if pick is None:
                rk.answer("t", cant_decide=True, round_seq=view.round, ms=int(secs * 1000))
            else:
                rk.answer("t", [pick], round_seq=view.round, ms=int(secs * 1000))
        lst = rk._list("t")
        cur = rk._current(lst)
        pairs = Pairs.of(*zip(*cur.history, strict=True))
        choices = Choices.of(cur.set_rounds)
        prior = Prior(**lst.settings["prior"])
        for h, hyper in HYPERS.items():
            fit = fit_pairs_learning_sigma(n, pairs, prior, hyper, choices=choices)
            out[h].append(fit.sigma)
        true_sd.append(float(np.std(np.array([theta[x] for x in names]) * slope)))
        answers.append(len(cur.history) + len(cur.set_rounds))
    med = {h: statistics.median(v) for h, v in out.items()}
    print(
        f"{kind:8s} answers {statistics.median(answers):.0f}; true sd {statistics.median(true_sd):.2f}; "
        f"learned sigma shipped {med['shipped']:.2f}, flat {med['flat']:.2f}"
    )
