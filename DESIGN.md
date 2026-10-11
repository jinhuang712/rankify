# Design

This document covers how rankify works and why it is built this way. The rules behind it are in [PHILOSOPHY.md](PHILOSOPHY.md). The command reference is in [rankify/cli/CLI.md](rankify/cli/CLI.md). Exact formulas, thresholds and table columns will live in the code and its tests, not here.

## The big picture

```text
 judge ──answer──> CLI / terminal UI ──add──> rounds (the log)
                        ^                         │
                        │ next round              │ every answer
                        │                         v
                     planner <──scores, ranges── fit
                        │
                        └──> forecast, in background ──> rounds left
```

You answer a round, and the answer is added to the log. The model is refitted to every answer in the log, which gives each item a score and a range. The planner uses those to choose the next round. In the background, the forecast estimates how many rounds are left. Everything except the log can be rebuilt from the log.

## Words

- **Score**: an item's strength on the Elo scale. 1500 is average. 100 points apart means the higher item wins about 64% of the time.
- **Confidence**: the chance that an item really belongs above the next one.
- **Could be**: where the item might really rank, as a 90% range.
- **Round**: one question. A round is a *pair* ("which is better?"), a *pick* ("which is best of these?") or a *rank* ("put these in order").
- **Mode**: how sure you need to be: Quick, Stable or Exact.

In code and docs we also say *list*, *item*, *judge*, *fit*, *planner* and *forecast*.

## The model

Each item has one hidden score. A single family of models explains every round type with those same scores. Bradley–Terry covers pairs. Plackett–Luce covers picks and full orderings, and it treats an ordering as "pick the best, then the best of the rest". Elo uses the same curve, so scores convert directly to the Elo scale.

Three additions keep the model honest:

- **"Can't decide" is a real answer.** For pairs we use Davidson's extension of Bradley–Terry, which models ties. In v1, "can't decide" in a pick or rank round is recorded but not used.
- **Position bias is measured.** Each display slot gets a small fitted bonus, so a habit of choosing the first item doesn't leak into the scores.
- **Every score starts in the middle, with a wide range.** This gives the fit a single answer and keeps new or rarely seen items from jumping around. The width of that starting range is learned from how consistent the judge is, so a very consistent judge's answers count for more.

The model has two known limits. It assumes taste lies on one axis. It also assumes that adding a third option doesn't change the odds between two others. Similar items can break the second assumption, so the planner keeps near-identical items out of pick rounds. The report flags answers the model can't explain, which is where either limit would show up.

## Fitting

After each round, the model is fitted to all answers at once. This is what makes the result independent of answer order, and it is the main difference from Elo, which updates one match at a time. An Elo update is one small step toward this same fit.

The fit starts from the previous scores, so one new answer needs only a few Newton steps. Each item's range comes from the curvature of the fit around its best value (the Laplace approximation). Score, Confidence and Could be all follow from the scores and their ranges. Two items that are confidently close become a confident tie, shown as `=`, and the planner stops asking about them.

**The prior width is learned.** Every score starts at Normal(0, σ²), and σ is learned from the answers (MacKay 1992). A consistent judge spreads items far apart, so σ grows and each answer counts for more. A judge who contradicts themself keeps σ narrow. The width maximizes the evidence, found by expectation-maximization over the Laplace posterior (Dempster, Laird & Rubin 1977) with Aitken's acceleration. A weak prior on log σ, centred at 1.5, stops σ from collapsing on lists with few answers. Like the scores, σ depends only on the set of answers.

## Choosing the next round

The planner looks for the question that teaches the most about the **order** per second of your time, about the part of the ranking your mode cares about. For now it asks pairs. Sets of three to five come in Phase 3.

For each candidate pair, it estimates the mutual information between your answer and which of the two items is really better. This is in the spirit of BALD (Houlsby et al. 2011), but aimed at the order. Plain BALD measures information about the scores, so it kept asking pairs whose order was already settled, just to sharpen the size of their gap. The order measure is zero for pairs whose order is known. It is also zero for pairs already known to be tied, whose answer is a coin flip that teaches nothing.

Each pair's information is weighted by how much the pair matters for the mode: the chance, over posterior draws, that either item really belongs to the part the mode settles. That part is the top 3 for Quick, the top quarter for Stable (plus a smaller weight for tier boundaries), and everything for Exact. The weighted information is then divided by how long the pair is expected to take you. That estimate comes from your own answer times, which grow on close calls (Moyer & Landauer 1967), with a flat guess until there are 20 timed answers.

**Every item gets a first look.** Before the planner judges any item unimportant, every item gets at least two answers: the least-seen item goes against its most informative partner. Without this, an item that has barely been compared sits mid-ranking with a wide range and never looks like a contender. In one benchmark list, the clearly best item lost its first comparison to a slip and was never asked about again.

The best candidate wins, and its display order is shuffled with the round's seed. The candidates the planner weighed are saved, so `rankify why` can explain the choice.

**Stopping.** The session stops when the mode's target is reached. It also stops when nothing is worth asking: even 8 more answers to the most useful pair would teach less than 0.1 bits about the order that matters. The test looks at several answers, not one, on purpose. A judge who gets a pair right 60% of the time teaches only about 0.03 bits per answer (1 − h(0.6)), but those bits add up. A one-answer test stopped far too early on crowded lists. The 0.1-bit threshold was tuned on hidden lists the benchmark never uses (EXPERIMENT.md).

Calibration lists (`--calibrate`) keep random pairs with swapped repeats. That is the design the calibration's bias correction simulates.

Multi-item rounds help only in some situations. Saha & Gopalan (2019) show that with noisy answers, "pick the best of k" is no faster than pairs, while ordering the top m items is about m times faster. So picks pay off mainly when one item clearly stands out, and orderings pay off when a few items are close. The planner doesn't need these as hard-coded rules. They fall out of the gain-per-second scoring.

## Modes

Each mode is a confidence target, not a fixed number of rounds.

- **Quick** stops when the winner is clear (90% Confidence over #2), the top 3 are fairly clear (80%), and no item below #3 could still be in the top 3 (its Could be range stays below). Everything else stays in rough tiers.
- **Stable** stops when the top of the list (about a quarter of it, at least 3 items) is in a confident order (90%), no item below could still reach it, and the rest falls into confident tiers.
- **Exact** stops when every neighbouring pair is in a confident order (95%) or is a confident tie.

In every mode, a confident tie (at least 90% likely to be within 30 Score points) counts as settled. The thresholds can be adjusted, and the benchmark will tune the defaults. `show` reports whether the list's mode has reached its target, and `next --mode` asks one session in another mode without changing the list.

## Rounds left

To estimate rounds left, rankify plays the rest of the session forward many times in simulation. Each time, it draws plausible "true" scores from the current fit, simulates your answers, and runs a cheap version of the planner until the mode's target is met. The spread of the round counts gives a range like "about 14 (10–19)". This runs in the background, and the screen shows the previous estimate until the new one is ready.

## Storage

All data lives in one local SQLite file.

The source of truth is a small set of tables: lists, items, judges and rounds. Each round records what was shown, in which order, the answer, how long it took, and its seed. Rounds are only ever added. An undo is a new round that cancels an earlier one. A removed item is hidden from the ranking, but its rounds stay in the fit, because they still say something about the other items.

Everything else is derived and can be rebuilt: fits (scores and ranges after each round), plans (what the planner considered), forecasts and logs. Each derived row records which engine version made it and which rounds it used. `rankify verify` rebuilds the derived rows and checks that they match.

## Code layout

```text
rankify/
  engine/     the math; no I/O
  store/      SQLite; no math
  service.py  ties the engine to the store; everything else calls this
  cli/        commands (see cli/CLI.md)
  tui/        the terminal UI
  report/     the agent report
  sim/        simulated judges, baselines, benchmark
tests/
```

The engine never touches the database, and the store never does math. The CLI, the terminal UI and the simulator all call the same engine.

## Agent report

The report gives an agent what it needs to dig deeper. It comes in Markdown and JSON, and contains:

- the ranking with Score, Confidence and Could be
- confident ties
- weak spots, meaning close neighbours that were never compared directly
- slow decisions, which mark close calls
- upsets the model can't explain
- position bias and judge consistency
- with several judges, where they disagree

An agent can also query the SQLite file directly.

## Speed

From answer to next round should take under 50 ms for lists of up to 200 items. That breaks down into about 5 ms to save, 10 ms to refit and 30 ms to plan. The forecast gets up to a second, in the background. Performance tests enforce these targets.

Measured on 2026-10-12, for 200 items:

- Saving an answer takes 0.02 ms.
- A refit with a fixed width takes 5 ms. Learning the width raises a warm refit to about 19 ms, over its 10 ms share.
- Answer to next round takes 41 ms at the median and 46 ms at the 95th percentile. That is inside the 50 ms target, with little to spare.
- Lists of 50 items or fewer take a few milliseconds per round.

## How the design applies the principles

The numbers refer to [PHILOSOPHY.md](PHILOSOPHY.md).

1. **Attention is scarce.** The planner scores rounds by information gain per second, skips predictable rounds, and stops when nothing clears the floor.
2. **Answers are evidence.** A probabilistic model, a learned judge consistency, and no hard transitive pruning. Answers the model can't explain are flagged, not dropped.
3. **Reproducible.** An append-only `rounds` table, one batch fit over all answers, a seed on every round, rebuildable caches, and `rankify verify`.
4. **Honest certainty.** Ranges on every score, Could be intervals, interval forecasts, and calibration tested in the benchmark.
5. **Proven before novel.** Bradley–Terry / Plackett–Luce at the core. New methods only in the planner, gated by the benchmark in [EXPERIMENT.md](EXPERIMENT.md).
6. **Keep up.** A 50 ms budget from answer to next round, warm-started fits, and the forecast in the background.

## References

The full list of books, papers and software is in the [README](README.md#references).
