"""Shipped fit (Laplace + 90%-sure gap scale) against EP, on practice lists (seeds 70000+):
rounds to the stop, the mode's target at the stop, #1 right, top-quarter pairs in order, and
seconds per session. Hidden scores either the benchmark's (1.5 x Student-t(3)) or a bell curve
with the same middle crowding (Normal, sd 1.70: the same interquartile range).
usage: ep_eval.py <worktree> <variants> <shapes> <judges> <n> <modes> <runs> [workers]
variants: laplace | ep;  shapes: t3 | normal"""

import itertools
import math
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])

NORMAL_SD = 1.5 * 0.7649 / 0.6745  # t(3)'s upper quartile is 0.7649, the normal's 0.6745


def setup():
    os.nice(10)
    import rankify.service as service
    from rankify.engine.forecast import Forecast

    service.forecast_rounds = lambda **kw: Forecast(0, 0, 0, None, 0, 0, 0.0)


def task(t):
    import rankify.bench as bench
    import rankify.service as service

    variant, shape, judge, n, mode, seed = t
    service.EP_FIT = variant == "ep"
    if shape == "normal":
        bench.hidden_scores = lambda names, rng, spread=None: {
            x: float(NORMAL_SD * rng.standard_normal()) for x in names
        }
    t0 = time.perf_counter()
    res = bench.run_one(f"rankify:{mode}", judge, n, seed, 20 * n)
    secs = time.perf_counter() - t0
    s = res.final_scores
    one = s[0] >= max(s) - bench.TIE_MARGIN
    k = max(3, math.ceil(len(s) / 4))
    pairs = [(x, y) for x, y in itertools.pairwise(s[:k]) if abs(x - y) >= bench.TIE_MARGIN]
    row = (res.rounds, res.flags[mode][-1], one, sum(x > y for x, y in pairs), len(pairs), secs)
    return (variant, shape, judge, mode), row


if __name__ == "__main__":
    variants, shapes, judges = (sys.argv[i].split(",") for i in (2, 3, 4))
    n = int(sys.argv[5])
    modes = sys.argv[6].split(",")
    runs = int(sys.argv[7])
    workers = int(sys.argv[8]) if len(sys.argv) > 8 else 2
    tasks = [
        (v, sh, j, n, m, 70000 + 1000 * n + r)
        for sh in shapes
        for j in judges
        for m in modes
        for v in variants
        for r in range(runs)
    ]
    by = {}
    with ProcessPoolExecutor(workers, initializer=setup) as ex:
        for key, row in ex.map(task, tasks):
            by.setdefault(key, []).append(row)
    for sh in shapes:
        print(f"== hidden scores: {sh}")
        for j in judges:
            for m in modes:
                for v in variants:
                    rows = by[(v, sh, j, m)]
                    share = sum(r[3] for r in rows) / max(1, sum(r[4] for r in rows))
                    print(
                        f"{j:8s} {m:6s} {v:7s} rounds {statistics.median(r[0] for r in rows):5.0f}  "
                        f"met {sum(r[1] for r in rows):2d}/{len(rows)}  #1 right {sum(r[2] for r in rows):2d}/{len(rows)}  "
                        f"top-quarter pairs {share:.0%}  {statistics.median(r[5] for r in rows):.1f} s"
                    )
            print()
