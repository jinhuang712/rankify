"""Where do EP's passes go? One normal-judge practice session to its stop, then the EP fit
with each inner EP run's passes and final damping logged.
usage: ep_profile.py <worktree> [judge]"""

import math
import os
import sys
import time

sys.path.insert(0, sys.argv[1])
os.nice(10)

import numpy as np  # noqa: E402

import rankify.engine.ep as ep  # noqa: E402
from rankify import store  # noqa: E402
from rankify.bench import Judge, hidden_scores  # noqa: E402
from rankify.engine.model import Pairs, Prior  # noqa: E402
from rankify.service import NothingToAsk, Rankify  # noqa: E402

kind = sys.argv[2] if len(sys.argv) > 2 else "normal"
n, seed = 20, 70000 + 20000
rng = np.random.default_rng(seed)
names = [f"item-{k:02d}" for k in range(n)]
theta = hidden_scores(names, rng, 1.5)
judge = Judge(theta, kind, np.random.default_rng([seed, 1]))
rk = Rankify(store.connect(":memory:"))
rk.create_list("t", "T", names, mode="quick", seed=seed)
for effort in range(400):
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

log = []
inner = ep._ep


def traced(post, sigma, y, beta, lam, ties, tol, max_sweeps=5000):
    out = inner(post, sigma, y, beta, lam, ties, tol, max_sweeps)
    log.append((sigma, beta, lam, out[3]))
    return out


ep._ep = traced
inner_step = ep._shared_step
inner_sigma = ep._best_log_sigma


def traced_step(stats, beta, lam, *args):
    nb, nl, h = inner_step(stats, beta, lam, *args)
    log.append(("shared move", max(abs(nb - beta), abs(nl - lam))))
    return nb, nl, h


def traced_sigma(spread, n, s, hyper):
    em = inner_sigma(spread, n, s, hyper)
    log.append(("sigma residual", em - s))
    return em


ep._shared_step = traced_step
ep._best_log_sigma = traced_sigma
t0 = time.perf_counter()
fit = ep.fit_pairs_ep(n, pairs, prior)
print(
    f"{len(pairs)} answers; {(time.perf_counter() - t0) * 1000:.0f} ms; {fit.iterations} passes; sigma {fit.sigma:.3f}"
)
for row in log:
    if len(row) == 4:
        print(f"  EP at sigma {row[0]:.10f}: {row[3]} passes", end="")
    else:
        print(f"; {row[0]} {row[1]:+.1e}", end="" if row[0] == "shared move" else "\n")
