"""What holds rankify back once its ranking is already right? For each session, find the round
from which the mode's target really holds to the end, then, over the rounds from there to the
stop, how often each stopping condition still failed, and which was satisfied last.
Practice seeds (70000+). usage: lag_diag.py <worktree> <judges> <n> <modes> <runs> [workers]"""

import os
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])


def conditions(mode, r):
    from rankify.engine import stop

    order = [p for p, _, _ in r.ranks]
    nb = stop.neighbours(r.theta * r.gap_scale, r.theta_cov, order)
    n = len(order)
    ok = (nb.confidence >= 0) & False
    if mode == "quick":
        need = [stop.QUICK_TOP, stop.QUICK_NEXT, stop.QUICK_NEXT]
        ok = [
            bool(nb.confidence[i] >= need[i] or nb.tie[i] >= stop.TIE_CONFIDENCE) for i in range(3)
        ]
        reach = all(lo > 3 for _, lo, _ in r.ranks[3:])
        return {
            "#1>#2 90%": ok[0],
            "#2>#3 80%": ok[1],
            "#3>#4 80%": ok[2],
            "none below reaches": reach,
        }
    k = stop.top_size(n)
    settled = nb.settled(stop.STABLE_LEVEL)[: min(k, n - 1)]
    out = {f"top pair {i + 1} 90%": bool(settled[i]) for i in range(len(settled))}
    out["tier cuts 90%"] = all(
        nb.confidence[b] >= stop.STABLE_LEVEL for b in stop.tier_boundaries(nb, k)
    )
    out["none below reaches"] = all(lo > k for _, lo, _ in r.ranks[k:])
    return out


def task(t):
    os.nice(10)
    import numpy as np

    from rankify import store
    from rankify.bench import Judge, hidden_scores, targets_met
    from rankify.service import NothingToAsk, Rankify

    judge_kind, n, mode, seed = t
    rng = np.random.default_rng(seed)
    names = [f"item-{k:02d}" for k in range(n)]
    theta = hidden_scores(names, rng, 1.5)
    judge = Judge(theta, judge_kind, np.random.default_rng([seed, 1]))
    rk = Rankify(store.connect(":memory:"))
    rk.create_list("t", "T", names, mode=mode, seed=seed)
    flags, conds, effort = [], [], 0
    for _ in range(20 * n):
        try:
            view = rk.next_round("t")
        except NothingToAsk:
            break
        pick, secs = judge.answer([i.name for i in view.items], effort)
        effort += 1
        if pick is None:
            rk.answer("t", cant_decide=True, round_seq=view.round, ms=int(secs * 1000))
        else:
            rk.answer("t", [pick], round_seq=view.round, ms=int(secs * 1000))
        r = rk._current(rk._list("t"))
        order = [names[p] for p, _, _ in r.ranks]
        flags.append(targets_met(order, theta)[mode])
        conds.append(conditions(mode, r))
    reached = bool(r.params["targets"][mode])
    return t, flags, conds, reached


if __name__ == "__main__":
    judges = sys.argv[2].split(",")
    n = int(sys.argv[3])
    modes = sys.argv[4].split(",")
    runs = int(sys.argv[5])
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    tasks = [(j, n, m, 70000 + 1000 * n + r) for j in judges for m in modes for r in range(runs)]
    by = {}
    with ProcessPoolExecutor(workers) as ex:
        for (j, _, m, _), flags, conds, reached in ex.map(task, tasks):
            by.setdefault((j, m), []).append((flags, conds, reached))
    for (j, m), sessions in by.items():
        fail, last, lags, right_at, stops, at_target = Counter(), Counter(), [], [], [], 0
        window = 0
        for flags, conds, reached in sessions:
            stop_round = len(flags)
            stops.append(stop_round)
            at_target += reached
            # first round from which the target holds to the end
            ra = next((i for i in range(stop_round) if all(flags[i:])), None)
            if ra is None:
                continue
            right_at.append(ra + 1)
            lags.append(stop_round - (ra + 1))
            for c in conds[ra:-1]:
                window += 1
                for name, ok in c.items():
                    fail[name] += not ok
            # the condition(s) satisfied last: false in the round before the stop
            if len(conds) >= 2:
                for name, ok in conds[-2].items():
                    if not ok:
                        last[name] += 1
        print(
            f"\n== {j} {m}: stop median {statistics.median(stops):.0f}, right-at median "
            f"{statistics.median(right_at) if right_at else float('nan'):.0f} ({len(right_at)}/{len(sessions)} right at the end), "
            f"stopped at target {at_target}/{len(sessions)}, lag median {statistics.median(lags) if lags else float('nan'):.0f}"
        )
        for name in sessions[0][1][0]:
            print(
                f"   {name:20s} failing in {fail[name] / max(1, window):4.0%} of lag rounds; last to hold in {last[name]} sessions"
            )
