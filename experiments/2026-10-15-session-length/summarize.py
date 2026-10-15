"""Tables from length_eval.py's JSON lines. usage: summarize.py <file.jsonl> [<file.jsonl> ...]"""

import json
import math
import statistics
import sys
from collections import defaultdict

rows = [json.loads(line) for f in sys.argv[1:] for line in open(f) if line.strip()]
errors = [r for r in rows if r["error"]]
rows = [r for r in rows if not r["error"]]
by = defaultdict(list)
for r in rows:
    by[(r["n"], r["mode"], r["judge"], r["variant"])].append(r)
variants = list(dict.fromkeys(r["variant"] for r in rows))
judges = list(dict.fromkeys(r["judge"] for r in rows))


def med(values):
    """Median, with not-reached as infinitely long; None when most lists never got there."""
    v = sorted(math.inf if x is None else x for x in values)
    m = statistics.median(v)
    return None if math.isinf(m) else m


def fmt(x, got, total):
    s = "—" if x is None else f"{x:.0f}"
    return s if got == total else f"{s} ({got})"


print(f"sessions {len(rows)}, crashed {len(errors)}\n")
for n in sorted({r["n"] for r in rows}):
    for mode in ("quick", "stable"):
        cells = {k: v for k, v in by.items() if k[0] == n and k[1] == mode}
        if not cells:
            continue
        total = len(next(iter(cells.values())))
        print(f"## {n} items, {mode.capitalize()} mode, {total} lists\n")
        print(
            "Rounds until the target is reached (median; lists reached in brackets when fewer):\n"
        )
        print("| Judge | " + " | ".join(variants) + " |")
        print("|---" * (len(variants) + 1) + "|")
        for j in judges:
            line = []
            for v in variants:
                rs = cells[(n, mode, j, v)]
                got = sum(r["reached"][mode] is not None for r in rs)
                line.append(fmt(med(r["reached"][mode] for r in rs), got, len(rs)))
            print(f"| {j} | " + " | ".join(line) + " |")
        print("\nRounds at rankify's own stop (median) · right at the stop · repeats:\n")
        print("| Judge | " + " | ".join(variants) + " |")
        print("|---" * (len(variants) + 1) + "|")
        for j in judges:
            line = []
            for v in variants:
                rs = cells[(n, mode, j, v)]
                stop = statistics.median(r["rounds"] for r in rs)
                right = sum(r["right_at_stop"][mode] for r in rs)
                rep = statistics.mean(r["repeats"] for r in rs)
                line.append(f"{stop:.0f} · {right}/{len(rs)} · {rep:.0%}")
            print(f"| {j} | " + " | ".join(line) + " |")
        for cp in ("20", "40"):
            print(
                f"\nAfter {cp} answers: lists where Quick holds · Stable holds · mean Kendall tau:\n"
            )
            print("| Judge | " + " | ".join(variants) + " |")
            print("|---" * (len(variants) + 1) + "|")
            for j in judges:
                line = []
                for v in variants:
                    rs = cells[(n, mode, j, v)]
                    q = sum(bool(r["at"][cp]["quick"]) for r in rs)
                    s = sum(bool(r["at"][cp]["stable"]) for r in rs)
                    tau = statistics.mean(r["at"][cp]["tau"] for r in rs)
                    line.append(f"{q} · {s} · {tau:.2f}")
                print(f"| {j} | " + " | ".join(line) + " |")
        print()
