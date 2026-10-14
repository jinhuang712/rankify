"""The full model (pairs with "can't decide" and the first-slot bonus): the spread rankify's
Laplace fit learns against our EP fit, on the answers of practice sessions run to their stop,
with the shipped starting belief. Also EP's time and passes.
usage: ep_check2.py <worktree> <judges> <n> <mode> <runs>"""

import math
import os
import statistics
import sys
import time

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])
os.nice(10)

import numpy as np  # noqa: E402

from rankify import store  # noqa: E402
from rankify.bench import HUMAN, MODEL_SLOPE, Judge, hidden_scores  # noqa: E402
from rankify.engine.ep import fit_pairs_ep  # noqa: E402
from rankify.engine.fit import fit_pairs_learning_sigma  # noqa: E402
from rankify.engine.model import Pairs, Prior  # noqa: E402
from rankify.service import NothingToAsk, Rankify  # noqa: E402

judges, n, mode, runs = sys.argv[2].split(","), int(sys.argv[3]), sys.argv[4], int(sys.argv[5])
for kind in judges:
    if kind in ("human", "noisy"):
        slope = 1.702 / (math.sqrt(2.0) * HUMAN.noise)
    else:
        slope = MODEL_SLOPE.get(kind, MODEL_SLOPE["normal"])
    rows = []
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
        prior = Prior(**lst.settings["prior"])
        lap = fit_pairs_learning_sigma(n, pairs, prior)
        t0 = time.perf_counter()
        ep = fit_pairs_ep(n, pairs, prior)
        ms = (time.perf_counter() - t0) * 1000
        true = np.array([theta[x] for x in names]) * slope
        order = np.argsort(-true)
        gap = lambda v: (v[order[0]] - v[order[3]]) / (true[order[0]] - true[order[3]])  # noqa: E731
        rows.append(
            (
                float(np.std(true)),
                lap.sigma,
                ep.sigma,
                gap(lap.theta),
                gap(ep.theta),
                len(pairs),
                ms,
                ep.iterations,
                lap.tie,
                ep.tie,
            )
        )
    med = [statistics.median(x[i] for x in rows) for i in range(10)]
    print(
        f"{kind:8s} answers {med[5]:.0f}; true sd {med[0]:.2f}; spread: Laplace {med[1]:.2f}, EP {med[2]:.2f}; "
        f"#1-#4 gap / true: Laplace {med[3]:.2f}, EP {med[4]:.2f}; tie weight Laplace {med[8]:.3f}, EP {med[9]:.3f}; "
        f"EP {med[6]:.0f} ms, {med[7]:.0f} passes (median)"
    )
