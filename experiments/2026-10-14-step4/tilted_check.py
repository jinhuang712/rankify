"""EP's per-answer moments against brute force: all three answers, a bonus, narrow to very wide
cavities, and the tie weight's derivatives against finite differences of log Z.
usage: tilted_check.py <worktree>"""

import math
import sys

sys.path.insert(0, sys.argv[1])

import numpy as np  # noqa: E402

from rankify.engine.ep import _Grid, _lik, _moments  # noqa: E402
from rankify.engine.model import A_WINS, B_WINS, TIE  # noqa: E402


def brute(mc, vc, y, beta, lam, ties):
    sd = math.sqrt(vc)
    lo, hi = min(mc - 14 * sd, -80.0 - beta), max(mc + 14 * sd, 80.0 - beta)
    s = np.linspace(lo, hi, 4_000_001)
    ll = _lik(s + beta, np.full_like(s, y), lam, ties)[0]
    logd = -((s - mc) ** 2) / (2 * vc) + ll
    top = logd.max()
    w = np.exp(logd - top)
    z = w.sum()
    mean = float(np.sum(w * s) / z)
    var = float(np.sum(w * (s - mean) ** 2) / z)
    logz = top + math.log(z * (s[1] - s[0])) - 0.5 * math.log(2 * math.pi * vc)
    return mean, var, logz


worst = {}
cases = [
    (0.0, 0.3),
    (1.0, 1.0),
    (2.0, 4.0),
    (-3.0, 10.0),
    (5.0, 100.0),
    (-20.0, 400.0),
    (0.0, 2000.0),
    (-60.0, 900.0),
    (40.0, 50.0),
]
for ties, lam in ((False, math.log(0.2)), (True, math.log(0.2)), (True, math.log(1.5))):
    grid = _Grid(lam, ties)
    for y in (A_WINS, B_WINS, TIE) if ties else (A_WINS, B_WINS):
        for beta in (0.0, 0.4):
            for mc, vc in cases:
                args = (np.array([mc]), np.array([vc]), np.array([y]))
                mean, var, e_gl, e_gl2, cross = (
                    float(v[0]) for v in _moments(*args, beta, lam, ties, grid)
                )
                m_ref, v_ref, lz = brute(mc, vc, y, beta, lam, ties)
                key = ("ties" if ties else "plain", y)
                errs = [abs(mean - m_ref) / math.sqrt(v_ref), abs(var - v_ref) / v_ref]
                if ties:
                    eps = 1e-4
                    lzp = brute(mc, vc, y, beta, lam + eps, ties)[2]
                    lzm = brute(mc, vc, y, beta, lam - eps, ties)[2]
                    d1 = (lzp - lzm) / (2 * eps)
                    d2 = (lzp - 2 * lz + lzm) / eps**2
                    errs += [abs(e_gl - d1), abs((e_gl2 - e_gl**2) - d2)]
                    mp = brute(mc, vc, y, beta, lam + eps, ties)[0]
                    mm = brute(mc, vc, y, beta, lam - eps, ties)[0]
                    errs += [abs(cross - (mp - mm) / (2 * eps))]
                prev = worst.get(key, [0.0] * len(errs))
                worst[key] = [max(p, e) for p, e in zip(prev, errs)]
                if max(errs[:2]) > 1e-6:
                    print(f"  large error: {key} beta={beta} mc={mc} vc={vc}: {errs}")
names = ["mean/sd", "var rel", "dlogZ/dlam", "d2logZ/dlam2", "dmean/dlam"]
for key, errs in worst.items():
    print(key, ", ".join(f"{n} {e:.1e}" for n, e in zip(names, errs)))
