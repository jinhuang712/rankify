# rankify

Rank anything by answering a few quick questions, with real statistics behind every answer.

> **Status: design phase.** There is no code yet. The documents below describe what we are building, the rules it follows, and how we will test it.

## Why

Ranking a whole list by hand is hard, and the result is hard to trust. Elo-style voting ("A or B?", many times) splits the work into small, separate judgments and lets math combine them. That idea is good, but Elo asks random pairs, repeats itself, and takes a long time to settle. With 20 items, random pairs need about 181 of the 190 possible pairs before the order is certain. A good sort needs 62.

rankify keeps the separate judgments and the math, and cuts the waste:

- Every question is chosen to be decisive: one whose answer rankify can't already predict.
- A round can be a pair, "pick the best of these", or "put these in order". The math picks whichever tells it the most per second of your time.
- Scores come from one model fitted to all answers at once, so the same answers always give the same result, in any order.
- You choose how sure you need to be (Quick, Stable or Exact), and rankify shows how many rounds are probably left.

## How it will look

```sh
rankify new nba "Best NBA player ever" --items players.txt
rankify play nba --mode stable
rankify show nba
```

```text
 #  Item                  Score  Confidence  Could be
 1  Michael Jordan         1712      74%       #1–#2
 2  LeBron James           1690      81%       #1–#3
 3  Kareem Abdul-Jabbar    1655      62%       #2–#5
```

The numbers above are made up. **Score** uses the Elo scale, with 1500 as the average. **Confidence** is the chance that an item really belongs above the next one. **Could be** is where the item might really rank, as a 90% range.

All commands are in [rankify/cli/CLI.md](rankify/cli/CLI.md).

## Documents

- [PROPOSAL.md](PROPOSAL.md): the pain points, what we want and don't want, and prior work
- [PHILOSOPHY.md](PHILOSOPHY.md): the principles behind the design
- [DESIGN.md](DESIGN.md): how it works and why
- [GOALS.md](GOALS.md): goals, how we measure them, and non-goals
- [EXPERIMENT.md](EXPERIMENT.md): how we benchmark it against Elo and other methods
- [ROADMAP.md](ROADMAP.md): phases, and the checks between them
- [rankify/cli/CLI.md](rankify/cli/CLI.md): the command reference

## Planned stack

Python, packaged with uv. Typer for the CLI, Textual for the terminal UI, numpy for the math, and a local SQLite file for all data.

## License

[MIT](LICENSE)
