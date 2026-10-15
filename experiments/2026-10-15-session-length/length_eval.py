"""Questions needed to reach a stable ranking, per fit and repeat rule, on practice lists
(seeds 70000 + 1000 × items + list number), benchmark-shaped scores.

For every variant, judge and mode: rounds until the mode's target is reached (the benchmark's
rule: it holds from then on for CONFIRM rounds, or to the method's end); rounds at rankify's own
stop and whether the target holds there; and how good the ranking is after a fixed number of
answers (the first real session ended at 20), as the share of lists whose Quick and Stable
targets hold then, and Kendall tau.

usage: length_eval.py <worktree> <variants> <judges> <n> <modes> <runs> [workers] [first_list]
variants: comma list of <fit>-<rule>, fit in {laplace, ep}, rule in {always, contradicted, once}"""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
sys.path.insert(0, sys.argv[1])

CHECKPOINTS = (10, 20, 30, 40, 60)


def setup():
    os.nice(10)
    import rankify.service as service
    from rankify.engine.forecast import Forecast

    service.forecast_rounds = lambda **kw: Forecast(0, 0, 0, None, 0, 0, 0.0)


def task(t):
    import rankify.bench as bench
    import rankify.engine.planner as planner
    import rankify.service as service

    variant, judge, n, mode, seed = t
    fit, rule = variant.split("-")
    service.EP_FIT = fit == "ep"
    planner.ASK_AGAIN = rule
    res = bench.run_one(f"rankify:{mode}", judge, n, seed, 20 * n)

    def at(r, series):
        # after r answers; a session that stopped earlier keeps its final ranking
        return None if not series else series[min(r, len(series)) - 1]

    return {
        "variant": variant,
        "judge": judge,
        "n": n,
        "mode": mode,
        "seed": seed,
        "error": res.error,
        "rounds": res.rounds,
        "finished": res.finished,
        "reached": {m: res.reached(m) for m in ("quick", "stable")},
        "right_at_stop": {m: res.flags[m][-1] if res.flags[m] else False for m in ("quick", "stable")},
        "repeats": sum(res.repeats) / max(1, res.rounds),
        "at": {
            r: {
                "quick": at(r, res.flags["quick"]),
                "stable": at(r, res.flags["stable"]),
                "tau": at(r, res.taus),
            }
            for r in CHECKPOINTS
        },
    }


if __name__ == "__main__":
    variants = sys.argv[2].split(",")
    judges = sys.argv[3].split(",")
    n = int(sys.argv[4])
    modes = sys.argv[5].split(",")
    runs = int(sys.argv[6])
    workers = int(sys.argv[7]) if len(sys.argv) > 7 else 2
    first = int(sys.argv[8]) if len(sys.argv) > 8 else 0
    seeds = [70000 + 1000 * n + r for r in range(first, first + runs)]
    tasks = [(v, j, n, m, s) for j in judges for m in modes for s in seeds for v in variants]
    with ProcessPoolExecutor(workers, initializer=setup) as ex:
        for row in ex.map(task, tasks):
            print(json.dumps(row), flush=True)
