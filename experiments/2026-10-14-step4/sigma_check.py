"""The prior width rankify learns against the true spread of the hidden scores on its own
(logit) scale, at the end of sessions. Also the gaps: true top gaps (logit) against the fit's.
usage: sigma_check.py <worktree> <judges> <n> <mode> <runs>"""

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
from rankify.service import NothingToAsk, Rankify  # noqa: E402

judges, n, mode, runs = sys.argv[2].split(","), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
for kind in judges:
    if kind in ("human", "noisy"):
        slope = 1.702 / (math.sqrt(2.0) * HUMAN.noise)
    else:
        slope = MODEL_SLOPE.get(kind, MODEL_SLOPE["normal"])
    out = []
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
        fit = rk._current(rk._list("t"))
        true = np.array([theta[x] for x in names]) * slope
        order = np.argsort(-true)
        top_true = true[order[0]] - true[order[3]]  # #1 to #4, logit
        top_fit = fit.theta[order[0]] - fit.theta[order[3]]
        mid = (fit.theta[order[7]] - fit.theta[order[12]]) / (true[order[7]] - true[order[12]])
        out.append(
            (fit.params["sigma"], float(np.std(true)), top_fit / top_true, fit.gap_scale, mid)
        )
    print(
        f"{kind:8s} learned sigma {statistics.median(o[0] for o in out):.2f}; true sd {statistics.median(o[1] for o in out):.2f}; "
        f"fit's #1-#4 gap / true {statistics.median(o[2] for o in out):.2f}; gap scale {statistics.median(o[3] for o in out):.2f}; #8-#13 gap / true {statistics.median(o[4] for o in out):.2f}"
    )
