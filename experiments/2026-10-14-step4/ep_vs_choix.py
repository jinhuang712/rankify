"""Our EP against choix.ep_pairwise on plain pairs with a fixed prior width.
usage: ep_vs_choix.py <worktree>"""

import sys
import time

sys.path.insert(0, sys.argv[1])

import choix  # noqa: E402
import numpy as np  # noqa: E402

from rankify.engine.ep import fit_pairs_ep  # noqa: E402
from rankify.engine.model import A_WINS, B_WINS, Pairs, Prior  # noqa: E402

for n, m, scale, sigma in (
    (8, 30, 1.0, 1.5),
    (12, 300, 1.5, 1.5),
    (20, 70, 8.0, 10.0),
    (20, 60, 50.0, 30.0),
):
    rng = np.random.default_rng(n * 1000 + m)
    theta = rng.normal(0, scale, n)
    a = rng.integers(0, n, m)
    b = (a + rng.integers(1, n, m)) % n
    p = 1 / (1 + np.exp(-(theta[a] - theta[b])))
    y = np.where(rng.random(m) < p, A_WINS, B_WINS)
    data = [(int(i), int(j)) if yy == A_WINS else (int(j), int(i)) for i, j, yy in zip(a, b, y)]
    t0 = time.perf_counter()
    fit = fit_pairs_ep(
        n, Pairs.of(a, b, y), Prior(sigma=sigma), ties=False, bias=False, learn_sigma=False
    )
    ms = (time.perf_counter() - t0) * 1000
    mean, cov = choix.ep_pairwise(n, data, 1 / sigma**2, model="logit", max_iter=1000)
    print(
        f"n={n} m={m} sigma={sigma}: max |mean diff| {np.max(np.abs(fit.theta - mean)):.2e} "
        f"(scale {np.max(np.abs(mean)):.2f}); max |cov diff| {np.max(np.abs(fit.theta_cov - cov)):.2e} "
        f"(scale {np.max(np.abs(cov)):.2f}); sweeps {fit.iterations}; {ms:.1f} ms"
    )
