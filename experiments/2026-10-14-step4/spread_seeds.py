"""Learned width over seeds: random pairs from a Bradley-Terry judge, EP vs Laplace, with a flat
and with the shipped starting belief. usage: spread_seeds.py <worktree>"""

import sys

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + "/tests")

import numpy as np  # noqa: E402

from rankify.engine.ep import fit_pairs_ep  # noqa: E402
from rankify.engine.fit import SigmaPrior, fit_pairs_learning_sigma  # noqa: E402
from test_engine import simulate_pairs  # noqa: E402

flat, shipped = SigmaPrior(1.5, 10.0), SigmaPrior()
for true_sd, m in ((1.5, 150), (3.0, 150), (8.0, 120), (8.0, 400)):
    rows = []
    for seed in range(8):
        rng = np.random.default_rng(1000 + seed)
        theta = rng.normal(0, true_sd, 20)
        pairs = simulate_pairs(theta, m, rng)
        real = float(np.sqrt(np.mean(theta**2)))
        r = [real]
        for hyper in (flat, shipped):
            r.append(fit_pairs_ep(20, pairs, hyper=hyper, ties=False, bias=False).sigma)
            r.append(fit_pairs_learning_sigma(20, pairs, hyper=hyper, ties=False, bias=False).sigma)
        rows.append(r)
    a = np.array(rows)
    ratio = a[:, 1:] / a[:, :1]
    print(f"true sd {true_sd}, {m} answers: learned / real, min-median-max over 8 seeds")
    for k, name in enumerate(("EP flat", "Laplace flat", "EP shipped", "Laplace shipped")):
        print(
            f"   {name:16s} {ratio[:, k].min():.2f} {np.median(ratio[:, k]):.2f} {ratio[:, k].max():.2f}"
        )
