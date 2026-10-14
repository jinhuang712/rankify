"""Is Could be really too wide, or do whole-number ranks make a 90% range hold more? At each
session's stop, for every item: does Could be hold the true rank, and what share of rankify's
own rank draws does it hold (the coverage it actually claims)? Practice seeds.
usage: couldbe_mass.py <worktree> <judges> <n> <modes> <runs> [workers]"""

import os
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])


def task(t):
    os.nice(10)
    import numpy as np

    from rankify import store
    from rankify.bench import Judge, hidden_scores
    from rankify.engine.stats import could_be
    from rankify.service import NothingToAsk, Rankify

    judge_kind, n, mode, seed = t
    rng = np.random.default_rng(seed)
    names = [f"item-{k:02d}" for k in range(n)]
    theta = hidden_scores(names, rng, 1.5)
    true_rank = {x: r + 1 for r, x in enumerate(sorted(names, key=lambda x: -theta[x]))}
    judge = Judge(theta, judge_kind, np.random.default_rng([seed, 1]))
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
    r = rk._current(rk._list("t"))
    shown = rk.ranking("t").items
    pos = [p for p, _, _ in r.ranks]
    mu = r.theta[pos] * r.gap_scale
    s = r.theta_cov[np.ix_(pos, pos)]
    draws = np.random.default_rng(seed).multivariate_normal(mu, s, size=4000)
    ranks = np.empty_like(draws, dtype=np.int64)
    ranks[np.arange(len(draws))[:, None], np.argsort(-draws, axis=1)] = np.arange(1, len(pos) + 1)
    rows = []
    for k, item in enumerate(shown):
        lo, hi = item.could_be
        held = float(np.mean((ranks[:, k] >= lo) & (ranks[:, k] <= hi)))
        rows.append((lo <= true_rank[item.name] <= hi, held, hi - lo + 1))
    return (judge_kind, mode), rows


if __name__ == "__main__":
    judges = sys.argv[2].split(",")
    n = int(sys.argv[3])
    modes = sys.argv[4].split(",")
    runs = int(sys.argv[5])
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    tasks = [(j, n, m, 70000 + 1000 * n + r) for j in judges for m in modes for r in range(runs)]
    by = {}
    with ProcessPoolExecutor(workers) as ex:
        for key, rows in ex.map(task, tasks):
            by.setdefault(key, []).extend(rows)
    for (j, m), rows in by.items():
        cover = sum(c for c, _, _ in rows) / len(rows)
        claimed = sum(h for _, h, _ in rows) / len(rows)
        single = sum(w == 1 for _, _, w in rows) / len(rows)
        print(
            f"{j:8s} {m:6s} Could be holds the true rank {cover:.0%}; rankify's own draws say {claimed:.0%}; one-rank ranges {single:.0%}"
        )
