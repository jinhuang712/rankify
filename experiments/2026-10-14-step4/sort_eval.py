"""rankify variants against sorting, on practice lists (seeds 70000+), benchmark-shaped scores.
For every method: simulated minutes until the mode's target is reached (the benchmark's rule:
it holds from then on for 10 rounds, or to the method's end). For rankify also: minutes and
rounds at its own stop, whether the target really holds there, and the share of repeats.
usage: sort_eval.py <worktree> <judges> <n> <modes> <runs> [workers]"""

import math
import os
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])

RANKIFY = ("old", "new-norep", "new-once")
SORTS = ("just-sort-it", "ford-johnson")


def setup():
    os.nice(10)
    import rankify.service as service
    from rankify.engine.forecast import Forecast

    service.forecast_rounds = lambda **kw: Forecast(0, 0, 0, None, 0, 0, 0.0)


def task(t):
    import rankify.bench as bench
    import rankify.engine.planner as planner
    import rankify.service as service

    method, judge, n, mode, seed = t
    if method in SORTS:
        res = bench.run_one(method, judge, n, seed, 20 * n)
        return [((method, judge, m), (res.minutes_to(m), None, None, None, None)) for m in mode]
    service.EP_FIT = method.startswith("new")
    planner.ASK_AGAIN = {"norep": "contradicted", "once": "once"}.get(
        method.split("-")[-1], "always"
    )
    res = bench.run_one(f"rankify:{mode}", judge, n, seed, 20 * n)
    stop = sum(res.seconds) / 60.0
    row = (
        res.minutes_to(mode),
        stop,
        res.rounds,
        res.flags[mode][-1],
        sum(res.repeats) / max(1, res.rounds),
    )
    return [((method, judge, mode), row)]


def med(values):
    """Median with not-reached as infinitely long; None when most lists never got there."""
    v = sorted(math.inf if x is None else x for x in values)
    m = statistics.median(v)
    return None if math.isinf(m) else m


if __name__ == "__main__":
    judges = sys.argv[2].split(",")
    n = int(sys.argv[3])
    modes = sys.argv[4].split(",")
    runs = int(sys.argv[5])
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    seeds = [70000 + 1000 * n + r for r in range(runs)]
    tasks = [(m, j, n, mode, s) for j in judges for m in RANKIFY for mode in modes for s in seeds]
    tasks += [(m, j, n, tuple(modes), s) for j in judges for m in SORTS for s in seeds]
    by = {}
    with ProcessPoolExecutor(workers, initializer=setup) as ex:
        for out in ex.map(task, tasks):
            for key, row in out:
                by.setdefault(key, []).append(row)
    for j in judges:
        for mode in modes:
            print(f"== {j} {mode}")
            for m in RANKIFY + SORTS:
                rows = by[(m, j, mode)]
                reached = med(r[0] for r in rows)
                got = sum(r[0] is not None for r in rows)
                line = f"   {m:13s} to target {'—' if reached is None else f'{reached:4.1f} min'} ({got}/{len(rows)})"
                if m in RANKIFY:
                    line += (
                        f"; stops at {statistics.median(r[1] for r in rows):4.1f} min, {statistics.median(r[2] for r in rows):3.0f} rounds, "
                        f"right at stop {sum(r[3] for r in rows):2d}/{len(rows)}, repeats {statistics.mean(r[4] for r in rows):.0%}"
                    )
                print(line)
        print()
