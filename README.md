# rankify

Rank anything by answering a few quick questions, with real statistics behind every answer.

> **Status: design phase.** There is no code yet. The documents below describe what we are building, the rules it must follow, and how we will test it.

## Why

Ranking a whole list by hand is hard, and the result is hard to trust. Elo-style voting ("A or B?", many times) splits the work into small, separate judgments and lets math combine them. That idea is good, but Elo asks random pairs, repeats itself, and needs a long time before the order settles. With 20 items, random pairs need about 181 of the 190 possible pairs before the order is certain. A good sort needs 62.

rankify keeps the separate judgments and the math, and fixes the waste:

- Every question is chosen to be decisive: one whose answer the system cannot already predict.
- A round can be a pair, "pick the best of these", or "put these in order". The math picks whichever tells it the most per second of your time.
- Scores come from one model fitted to all answers at once, so the same answers always give the same result, in any order.
- You choose how sure you need to be (Quick, Stable or Exact), and rankify shows how many rounds are probably left.

## How it will look

```sh
rankify new nba "Best NBA player ever" --items players.txt
rankify play nba --mode stable          # interactive terminal UI
rankify show nba                        # ranking table
rankify report nba --format md          # report for an AI agent
```

```text
 Best NBA player ever                  Stable · ~14 rounds left (10–19)
 ──────────────────────────────────────────────────────────────────────
 Round 23 · Put these in order, best first

   1  Michael Jordan
   2  LeBron James
   3  Kareem Abdul-Jabbar

 > 2 1 3                    [t] can't decide   [u] undo   [r] ranking
```

```text
 #  Item                  Score  Confidence  Could be
 1  Michael Jordan         1712      74%       #1–#2
 2  LeBron James           1690      81%       #1–#3
 3  Kareem Abdul-Jabbar    1655      62%       #2–#5
```

The numbers above are made up.

| Word | Meaning |
|---|---|
| Score | Same scale as Elo, with 1500 as the average. 100 points apart means the higher item wins about 64% of the time. 200 points apart means about 76%. |
| Confidence | The chance that this item really belongs above the next one. |
| Could be | Where the item might really rank, as a 90% range. |

## Planned stack

Python, packaged with uv. Typer for the CLI, Textual for the terminal UI, numpy for the math, and a local SQLite file for all data. See [DESIGN.md](DESIGN.md).

## Documents

| Document | Contents |
|---|---|
| [PROPOSAL.md](PROPOSAL.md) | Pain points, what we want, what we don't want, prior art |
| [GOALS.md](GOALS.md) | Goals, non-goals, and how we measure success |
| [DESIGN.md](DESIGN.md) | Principles we must never break, and the design |
| [EXPERIMENT.md](EXPERIMENT.md) | How we benchmark against Elo and other methods |
| [ROADMAP.md](ROADMAP.md) | Phases and the decision gates between them |

## License

Not chosen yet.
