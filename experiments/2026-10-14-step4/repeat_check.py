"""How often does rankify ask a pair it has already asked? Practice lists, sessions to the stop,
old formula (shipped) against the new one (EP). Counts rounds that repeat an earlier pair (either
side first), and among those, how often the earlier answers had all gone the same way.
usage: repeat_check.py <worktree> <judges> <n> <modes> <runs> [workers]"""

import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])


def setup():
    os.nice(10)
    import rankify.service as service
    from rankify.engine.forecast import Forecast

    service.forecast_rounds = lambda **kw: Forecast(0, 0, 0, None, 0, 0, 0.0)


def task(t):
    import numpy as np

    import rankify.service as service
    from rankify import store
    from rankify.bench import Judge, hidden_scores
    from rankify.engine.model import A_WINS, B_WINS
    from rankify.service import NothingToAsk, Rankify

    variant, kind, n, mode, seed = t
    service.EP_FIT = variant == "new"
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
    hist = rk._current(rk._list("t")).history
    seen: dict = {}
    repeats = same_way = 0
    for a, b, y in hist:
        key = (min(a, b), max(a, b))
        winner = a if y == A_WINS else b if y == B_WINS else None
        before = seen.get(key, [])
        if before:
            repeats += 1
            same_way += len(set(before)) == 1 and before[0] is not None
        seen[key] = before + [winner]
    most = max((len(v) for v in seen.values()), default=0)
    return (variant, kind, mode), (len(hist), repeats, same_way, most)


if __name__ == "__main__":
    judges = sys.argv[2].split(",")
    n = int(sys.argv[3])
    modes = sys.argv[4].split(",")
    runs = int(sys.argv[5])
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    tasks = [
        (v, j, n, m, 70000 + 1000 * n + r)
        for j in judges
        for m in modes
        for v in ("old", "new")
        for r in range(runs)
    ]
    by = {}
    with ProcessPoolExecutor(workers, initializer=setup) as ex:
        for key, row in ex.map(task, tasks):
            by.setdefault(key, []).append(row)
    for j in judges:
        for m in modes:
            for v in ("old", "new"):
                rows = by[(v, j, m)]
                total = sum(r[0] for r in rows)
                rep = sum(r[1] for r in rows)
                print(
                    f"{j:8s} {m:6s} {v}: {rep / total:4.0%} of rounds repeat a pair "
                    f"({rep} of {total}); after one-sided answers {sum(r[2] for r in rows)}; "
                    f"most times one pair was asked: median {statistics.median(r[3] for r in rows):.0f}, max {max(r[3] for r in rows)}"
                )
