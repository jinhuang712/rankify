"""Repeats allowed (shipped) against "ask a pair again only when contradicted", with the old
formula and the new one (EP), on practice lists (seeds 70000+), benchmark-shaped scores:
rounds to the stop, share of rounds that repeat a pair, whether the target really holds at
the stop, and why the session stopped (target reached, or nothing left worth asking).
usage: norep_eval.py <worktree> <variants> <judges> <n> <modes> <runs> [workers]
variants: old | old-norep | new | new-norep | new-once"""

import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])

STOPS: list = []


def setup():
    os.nice(10)
    import rankify.service as service
    from rankify.engine.forecast import Forecast

    service.forecast_rounds = lambda **kw: Forecast(0, 0, 0, None, 0, 0, 0.0)
    inner = service.Rankify.next_round

    def next_round(self, *a, **kw):
        try:
            return inner(self, *a, **kw)
        except service.NothingToAsk as e:
            STOPS.append(str(e).split(": ")[-1])
            raise

    service.Rankify.next_round = next_round


def task(t):
    import rankify.bench as bench
    import rankify.engine.planner as planner
    import rankify.service as service

    variant, judge, n, mode, seed = t
    service.EP_FIT = variant.startswith("new")
    planner.ASK_AGAIN = {"norep": "contradicted", "once": "once"}.get(
        variant.split("-")[-1], "always"
    )
    STOPS.clear()
    res = bench.run_one(f"rankify:{mode}", judge, n, seed, 20 * n)
    why = STOPS[-1] if STOPS else "budget"
    return (variant, judge, mode), (res.rounds, sum(res.repeats), res.flags[mode][-1], why)


if __name__ == "__main__":
    variants = sys.argv[2].split(",")
    judges = sys.argv[3].split(",")
    n = int(sys.argv[4])
    modes = sys.argv[5].split(",")
    runs = int(sys.argv[6])
    workers = int(sys.argv[7]) if len(sys.argv) > 7 else 2
    tasks = [
        (v, j, n, m, 70000 + 1000 * n + r)
        for j in judges
        for m in modes
        for v in variants
        for r in range(runs)
    ]
    by = {}
    with ProcessPoolExecutor(workers, initializer=setup) as ex:
        for key, row in ex.map(task, tasks):
            by.setdefault(key, []).append(row)
    for j in judges:
        for m in modes:
            for v in variants:
                rows = by[(v, j, m)]
                total = sum(r[0] for r in rows)
                print(
                    f"{j:8s} {m:6s} {v:9s} rounds {statistics.median(r[0] for r in rows):4.0f}  "
                    f"repeats {sum(r[1] for r in rows) / max(1, total):4.0%}  "
                    f"really right {sum(r[2] for r in rows):2d}/{len(rows)}  "
                    f"stopped at target {sum(r[3] == 'target reached' for r in rows):2d}/{len(rows)}"
                )
            print()
