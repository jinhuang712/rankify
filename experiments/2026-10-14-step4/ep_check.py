"""Does expectation propagation learn the spread that Laplace misses? Run sessions to their stop,
keep the decided pair answers, and learn the prior width by EM twice: over rankify's Laplace
posterior (no ties, no position bias, flat hyperprior) and over choix's EP posterior.
usage: ep_check.py <worktree> <judges> <n> <mode> <runs>"""

import math
import os
import statistics
import sys

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])
os.nice(10)

import choix  # noqa: E402
import numpy as np  # noqa: E402

from rankify import store  # noqa: E402
from rankify.bench import HUMAN, MODEL_SLOPE, Judge, hidden_scores  # noqa: E402
from rankify.engine.fit import SigmaPrior, fit_pairs_learning_sigma  # noqa: E402
from rankify.engine.model import A_WINS, B_WINS, Pairs, Prior  # noqa: E402
from rankify.service import NothingToAsk, Rankify  # noqa: E402


def ep_sigma(n, data, start=1.5, rounds=400):
    s2 = start**2
    state = None
    for _ in range(rounds):
        mean, cov = choix.ep_pairwise(n, data, 1.0 / s2, model="logit", max_iter=200)
        new = (float(mean @ mean) + float(np.trace(cov))) / n
        if abs(math.log(new / s2)) < 1e-6:
            return math.sqrt(new), mean, cov
        s2 = new
    return math.sqrt(s2), mean, cov


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
        cur = rk._current(rk._list("t"))
        decided = [(a, b, y) for a, b, y in cur.history if y in (A_WINS, B_WINS)]
        data = [(a, b) if y == A_WINS else (b, a) for a, b, y in decided]
        pairs = Pairs.of(*zip(*decided, strict=True))
        lap = fit_pairs_learning_sigma(
            n, pairs, Prior(), SigmaPrior(1.5, 10.0), ties=False, bias=False
        )
        ep, mean, cov = ep_sigma(n, data)
        true = np.array([theta[x] for x in names]) * slope
        order = np.argsort(-true)
        gap = lambda v: (v[order[0]] - v[order[3]]) / (true[order[0]] - true[order[3]])  # noqa: E731
        rows.append((float(np.std(true)), lap.sigma, ep, gap(lap.theta), gap(mean), len(data)))
    med = [statistics.median(x[i] for x in rows) for i in range(6)]
    print(
        f"{kind:8s} decided pairs {med[5]:.0f}; true sd {med[0]:.2f}; spread learned: Laplace {med[1]:.2f}, EP {med[2]:.2f}; "
        f"#1-#4 gap / true: Laplace {med[3]:.2f}, EP {med[4]:.2f}"
    )
