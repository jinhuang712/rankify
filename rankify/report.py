"""The agent report: what an agent (or a curious person) needs to dig into a ranking.

``build`` gathers it as plain data, which is the JSON form; ``markdown`` renders it. Every
judgement in the report comes from the list's fit and answer log, so rebuilding the report
from the same answers gives the same report (apart from the rounds-left forecast's timing).
"""

import statistics
from collections import Counter, defaultdict
from itertools import combinations, pairwise

import numpy as np

from rankify import store
from rankify.engine import stop
from rankify.engine.stats import SCORE_SCALE

UPSET_CHANCE = 0.1  # an answer the final scores give less than this chance is an upset
SLOW_FACTOR = 2.0  # a decision this many times slower than the judge's median is slow
MIN_TIMED = 5  # timed answers of one kind and size before "slow" means anything
SHOWN = 10  # longest list in each section


def _statements(rounds, pos):
    """Every "a beat b" an answer says, as (round, a, b) in item positions. A pick says the
    pick beat each other item; an ordering says each item beat every one below it."""
    out = []
    for r in rounds:
        if r.outcome != "answered":
            continue
        if r.kind == "pick":
            best = r.answer[0]
            out += [(r, pos[best], pos[x]) for x in r.shown if x != best]
        else:  # a pair or a full ordering, best first
            out += [(r, pos[a], pos[b]) for a, b in combinations(r.answer, 2)]
    return out


def build(rk, slug: str) -> dict:
    """The report for one list, as plain data."""
    lst = rk._list(slug)
    ranking = rk.ranking(slug)
    forecast = rk.forecast(slug)
    data = {
        "list": lst.slug,
        "title": lst.title,
        "method": ranking.method,
        "mode": ranking.mode,
        "answers": ranking.answers,
        "target_reached": ranking.target_reached,
        "rounds_left": None if forecast is None else forecast.as_dict(),
        "ranking": [
            {
                "rank": i.rank,
                "name": i.name,
                "score": i.score,
                "confidence": i.confidence,
                "could_be": i.could_be,
            }
            for i in ranking.items
        ],
        "ties": [],
        "weak_spots": [],
        "slow": [],
        "upsets": [],
        "judge": {},
        "judges": [],
        "disagreements": [],
    }
    r = rk._current(lst)
    items = store.items(rk.conn, lst.id)
    name = {k: it.name for k, it in enumerate(items)}
    pos = {iid: k for k, iid in enumerate(r.item_ids)}
    rounds = store.effective_rounds(rk.conn, lst.id)
    numbers = store.round_numbers(rk.conn, lst.id)
    judges = store.judge_names(rk.conn)
    said = _statements(rounds, pos)

    def number(round_row) -> int | None:
        return numbers.get(round_row.query_id)

    data["slow"] = _slow(rounds, numbers, name, pos)
    data["judges"], data["disagreements"] = _judges(said, judges, name)
    if r.theta is None:  # Elo and the sorts have no scores with ranges to judge by
        return data

    theta, cov = r.theta, r.theta_cov
    order = [p for p, _, _ in r.ranks]
    nb = stop.neighbours(theta, cov, order)
    level = stop.EXACT_LEVEL if ranking.mode == "exact" else stop.STABLE_LEVEL
    compared = {frozenset((a, b)) for _, a, b in said}
    compared |= {
        frozenset((pos[x.shown[0]], pos[x.shown[1]]))
        for x in rounds
        if x.kind == "pair" and x.outcome == "cant_decide"
    }
    for k, (upper, lower) in enumerate(pairwise(order)):
        pair = {"upper": name[upper], "lower": name[lower]}
        if nb.tie[k] >= stop.TIE_CONFIDENCE:
            data["ties"].append(pair | {"chance": float(nb.tie[k])})
        elif nb.confidence[k] < level and frozenset((upper, lower)) not in compared:
            data["weak_spots"].append(pair | {"rank": k + 1, "confidence": float(nb.confidence[k])})

    agree, expected, upsets = 0, 0.0, []
    for round_row, a, b in said:
        p = 1.0 / (1.0 + np.exp(-(theta[a] - theta[b])))  # chance a beats b, final scores
        agree += theta[a] > theta[b]
        expected += max(p, 1 - p)
        if p < UPSET_CHANCE:
            upsets.append(
                {"round": number(round_row), "winner": name[a], "loser": name[b], "chance": p}
            )
    data["upsets"] = sorted(upsets, key=lambda u: u["chance"])[:SHOWN]
    data["judge"] = {
        "position_bias": r.params.get("bias_points"),
        "tie_weight": r.params.get("tie_weight"),
        "spread": r.params.get("sigma"),
        "agreement": agree / len(said) if said else None,
        "expected_agreement": expected / len(said) if said else None,
        "statements": len(said),
    }
    return data


def _slow(rounds, numbers, name, pos) -> list[dict]:
    """Answers that took much longer than the same judge's usual for the same kind and size
    of round (ordering five items takes longer than a pair): close calls, or hard choices."""
    groups: dict[tuple, list] = defaultdict(list)
    for r in rounds:
        if r.ms:
            groups[(r.judge_id, r.kind, len(r.shown))].append(r)
    slow = []
    for group in groups.values():
        if len(group) >= MIN_TIMED:
            usual = statistics.median(r.ms for r in group)
            slow += [(r, usual) for r in group if r.ms > SLOW_FACTOR * usual]
    slow.sort(key=lambda pair: -pair[0].ms / pair[1])
    return [
        {
            "round": numbers.get(r.query_id),
            "kind": r.kind,
            "items": [name[pos[i]] for i in r.shown],
            "answer": None if r.answer is None else [name[pos[i]] for i in r.answer],
            "seconds": r.ms / 1000,
            "usual_seconds": usual / 1000,
        }
        for r, usual in slow[:SHOWN]
    ]


def _judges(said, judges, name) -> tuple[list[dict], list[dict]]:
    """Answers per judge, and pairs on which judges' answers point opposite ways."""
    by_judge: Counter = Counter()
    votes: dict[frozenset, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for round_row, a, b in said:  # +1 when the lower-numbered item won
        by_judge[round_row.judge_id] += 1
        votes[frozenset((a, b))][round_row.judge_id] += 1 if a < b else -1
    rows = [{"judge": judges[j], "statements": c} for j, c in sorted(by_judge.items())]
    split = []
    if len(by_judge) > 1:
        for pair, per in votes.items():
            leans = {j: v for j, v in per.items() if v != 0}
            if len({v > 0 for v in leans.values()}) > 1:
                lo, hi = sorted(pair)
                split.append(
                    {
                        "items": [name[lo], name[hi]],
                        "for_first": sorted(judges[j] for j, v in leans.items() if v > 0),
                        "for_second": sorted(judges[j] for j, v in leans.items() if v < 0),
                    }
                )
    return rows, split[:SHOWN]


# ---------------------------------------------------------------- Markdown


def _answer_text(kind: str, answer: list[str] | None) -> str:
    if answer is None:
        return "Couldn't decide."
    if kind == "rank":
        return "Order: " + " > ".join(answer) + "."
    return f"Picked {answer[0]}."


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def markdown(data: dict) -> str:
    target = {True: "reached", False: "not reached yet", None: "not tracked"}[
        data["target_reached"]
    ]
    left = data["rounds_left"]
    lines = [
        f"# Ranking report: {data['title']} (`{data['list']}`)",
        "",
        f"- Method: {data['method']}. Mode: {data['mode']}, target {target}.",
        f"- Answers: {data['answers']}.",
    ]
    if left:
        if left["median"] is None:
            lines.append(f"- Rounds left: at least {left['at_least']}.")
        else:
            high = "or more" if left["high"] is None else f"to {left['high']}"
            lines.append(f"- Rounds left: about {left['median']} ({left['low']} {high}).")
    lines += [
        "",
        "## Ranking",
        "",
        "| # | Item | Score | Confidence | Could be |",
        "|---|---|---|---|---|",
    ]
    for i in data["ranking"]:
        score = "—" if i["score"] is None else f"{i['score']:.0f}"
        could = "—" if i["could_be"] is None else f"{i['could_be'][0]}–{i['could_be'][1]}"
        lines.append(f"| {i['rank']} | {i['name']} | {score} | {_pct(i['confidence'])} | {could} |")
    lines += [
        "",
        (
            "Confidence is the chance that an item really is better than the next one. Could be "
            "is the range its true rank falls in, 90% of the time."
        ),
    ]

    def section(title: str, rows: list[str], empty: str) -> None:
        lines.extend(["", f"## {title}", ""])
        lines.extend(rows or [empty])

    section(
        "Confident ties",
        [
            f"- {t['upper']} = {t['lower']} ({t['chance']:.0%} likely within 30 Score points)"
            for t in data["ties"]
        ],
        "None.",
    )
    section(
        "Weak spots",
        [
            f"- #{w['rank']} {w['upper']} over {w['lower']}: {w['confidence']:.0%} confident, "
            "never compared directly."
            for w in data["weak_spots"]
        ],
        "None: every neighbour pair below the mode's confidence level has been compared directly.",
    )
    section(
        "Slow decisions",
        [
            f"- Round {s['round']} ({s['kind']}): {', '.join(s['items'])}. "
            f"{s['seconds']:.1f} s against a usual {s['usual_seconds']:.1f} s. "
            + _answer_text(s["kind"], s["answer"])
            for s in data["slow"]
        ],
        "None, or too few timed answers to tell.",
    )
    section(
        "Upsets the final scores can't explain",
        [
            f"- Round {u['round']}: {u['winner']} beat {u['loser']}, a {u['chance']:.0%} chance."
            for u in data["upsets"]
        ],
        f"None: every answer had at least a {UPSET_CHANCE:.0%} chance under the final scores.",
    )
    j = data["judge"]
    if j:
        bias = j["position_bias"]
        lines += [
            "",
            "## The judge",
            "",
            f"- Position bias: the item shown first gets {bias:+.0f} Score points."
            if bias is not None
            else "- Position bias: not measured.",
            (
                f"- Consistency: {_pct(j['agreement'])} of {j['statements']} pairwise statements "
                f"agree with the final ranking. If the model were exactly right, about "
                f"{_pct(j['expected_agreement'])} would."
            ),
        ]
        if j["spread"] is not None:
            lines.append(
                f"- Spread: scores are fitted with a prior width of {j['spread']:.2f} "
                f"({j['spread'] * SCORE_SCALE:.0f} Score points). A consistent judge spreads "
                "items wider."
            )
        if j["tie_weight"] is not None:
            lines.append(f'- "Can\'t decide" weight: {j["tie_weight"]:.2f}.')
    if len(data["judges"]) > 1:
        section(
            "Judges",
            [f"- {x['judge']}: {x['statements']} pairwise statements" for x in data["judges"]]
            + [
                f"- Split on {d['items'][0]} vs {d['items'][1]}: "
                f"{', '.join(d['for_first'])} for the first, "
                f"{', '.join(d['for_second'])} for the second."
                for d in data["disagreements"]
            ],
            "",
        )
    lines += [
        "",
        "## Going further",
        "",
        (
            "Every answer is in the SQLite file, table `rounds` (append-only; an undo is a new row). "
            "`rankify why <list> --round <n>` explains why a round was asked."
        ),
        "",
    ]
    return "\n".join(lines)
