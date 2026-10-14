"""Who blocks "nothing below reaches", and what does the joint chance look like? Over the rounds
after the ranking is already right and before the stop: for items below the top k, each one's
chance of really being in the top k (from 4000 draws), how many items sit at or above 5%, how
often those blockers were shown, and the joint chance that any item below is really in the top
k. Practice seeds. usage: reach_diag.py <worktree> <judges> <n> <modes> <runs> [workers]"""

import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])


def task(t):
    os.nice(10)
    import numpy as np

    from rankify import store
    from rankify.bench import Judge, hidden_scores, targets_met
    from rankify.engine import stop
    from rankify.service import NothingToAsk, Rankify, _looks

    judge_kind, n, mode, seed = t
    rng = np.random.default_rng(seed)
    names = [f"item-{k:02d}" for k in range(n)]
    theta = hidden_scores(names, rng, 1.5)
    judge = Judge(theta, judge_kind, np.random.default_rng([seed, 1]))
    rk = Rankify(store.connect(":memory:"))
    rk.create_list("t", "T", names, mode=mode, seed=seed)
    k = 3 if mode == "quick" else stop.top_size(n)
    rows, flags = [], []
    draw_rng = np.random.default_rng([seed, 9])
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
        pos = [p for p, _, _ in r.ranks]
        flags.append(targets_met([names[p] for p in pos], theta)[mode])
        mu = r.theta[pos] * r.gap_scale
        s = r.theta_cov[np.ix_(pos, pos)]
        d = draw_rng.multivariate_normal(mu, s, size=4000, method="cholesky")
        top = np.argsort(-d, axis=1)[:, :k]
        in_top = np.zeros((len(d), len(pos)), dtype=bool)
        in_top[np.arange(len(d))[:, None], top] = True
        p_in = in_top.mean(axis=0)  # each item's chance of really being in the top k
        below = np.arange(k, len(pos))
        blockers = below[p_in[below] >= 0.05]
        looks = _looks(r)
        rows.append(
            {
                "max_p": float(p_in[below].max()),
                "n_block": len(blockers),
                "looks": [looks[pos[b]] for b in blockers],
                "joint": float(in_top[:, below].any(axis=1).mean()),
                "first_right": float(np.mean(np.argmax(d, axis=1) == 0)),
            }
        )
    ra = next((i for i in range(len(flags)) if all(flags[i:])), None)
    return (judge_kind, mode), rows, ra


if __name__ == "__main__":
    judges = sys.argv[2].split(",")
    n = int(sys.argv[3])
    modes = sys.argv[4].split(",")
    runs = int(sys.argv[5])
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    tasks = [(j, n, m, 70000 + 1000 * n + r) for j in judges for m in modes for r in range(runs)]
    by = {}
    with ProcessPoolExecutor(workers) as ex:
        for key, rows, ra in ex.map(task, tasks):
            by.setdefault(key, []).append((rows, ra))
    for (j, m), sessions in by.items():
        lag = [row for rows, ra in sessions if ra is not None for row in rows[ra:-1]]
        end = [rows[-1] for rows, _ in sessions]
        looks = [x for row in lag for x in row["looks"]]
        print(f"\n== {j} {m}: {len(lag)} lag rounds")
        if lag:
            print(
                f"   blockers per round: median {statistics.median(r['n_block'] for r in lag):.0f}; "
                f"their looks: median {statistics.median(looks) if looks else 0:.0f}, "
                f"share with 1-2 looks {sum(x <= 2 for x in looks) / max(1, len(looks)):.0%}"
            )
            print(
                f"   largest single chance below: median {statistics.median(r['max_p'] for r in lag):.1%}; "
                f"joint chance any below is really in: median {statistics.median(r['joint'] for r in lag):.1%}"
            )
        print(
            f"   at the stop: joint chance any below in: median {statistics.median(r['joint'] for r in end):.1%}, "
            f"P(#1 right) median {statistics.median(r['first_right'] for r in end):.1%}"
        )
