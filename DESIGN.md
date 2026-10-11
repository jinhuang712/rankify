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

## Choosing the next round

The planner looks for the question that teaches the most per second of your time, about the part of the ranking your mode cares about.

It starts from the items in that part whose order is still in doubt, and builds candidate rounds from them: pairs first, then sets of three to five. For each candidate and each round type, it estimates how much the answer would reduce uncertainty. The measure is BALD (expected information gain). BALD is smarter than "pick the pair closest to 50/50": two items already known to be tied give a 50/50 answer but teach nothing, and BALD sees that. The gain is then divided by how long that kind of round takes this judge, based on their own timing history. Defaults apply until there is history.

The best candidate wins, and its display order is shuffled with the round's seed. The candidates the planner weighed are saved, so `rankify why` can explain the choice. If even the best candidate is below a small floor, the session stops, because nothing left is worth asking.

Multi-item rounds help only in some situations. Saha & Gopalan (2019) show that with noisy answers, "pick the best of k" is no faster than pairs, while ordering the top m items is about m times faster. So picks pay off mainly when one item clearly stands out, and orderings pay off when a few items are close. The planner doesn't need these as hard-coded rules. They fall out of the gain-per-second scoring.

## Modes

Each mode is a confidence target, not a fixed number of rounds.

- **Quick** stops when the winner is clear (90% Confidence over #2) and the top 3 are fairly clear (80%). Everything else stays in rough tiers.
- **Stable** stops when the top of the list (about a quarter of it, at least 3 items) is in a confident order (90%), and the rest falls into confident tiers.
- **Exact** stops when every neighbouring pair is in a confident order (95%) or is a confident tie.

You can adjust the thresholds. The benchmark will tune the defaults.

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

From answer to next round should take under 50 ms for lists of up to 200 items. That breaks down into about 5 ms to save, 10 ms to refit and 30 ms to plan. The forecast gets up to a second, in the background. These are targets until measured, and performance tests will enforce them.

## How the design applies the principles

The numbers refer to [PHILOSOPHY.md](PHILOSOPHY.md).

1. **Attention is scarce.** The planner scores rounds by information gain per second, skips predictable rounds, and stops when nothing clears the floor.
2. **Answers are evidence.** A probabilistic model, a learned judge consistency, and no hard transitive pruning. Answers the model can't explain are flagged, not dropped.
3. **Reproducible.** An append-only `rounds` table, one batch fit over all answers, a seed on every round, rebuildable caches, and `rankify verify`.
4. **Honest certainty.** Ranges on every score, Could be intervals, interval forecasts, and calibration tested in the benchmark.
5. **Proven before novel.** Bradley–Terry / Plackett–Luce at the core. New methods only in the planner, gated by the benchmark in [EXPERIMENT.md](EXPERIMENT.md).
6. **Keep up.** A 50 ms budget from answer to next round, warm-started fits, and the forecast in the background.

## References

- Bradley, R. A. & Terry, M. E. (1952). Rank analysis of incomplete block designs. *Biometrika*.
- Luce, R. D. (1959). *Individual Choice Behavior*.
- Plackett, R. L. (1975). The analysis of permutations. *Applied Statistics*.
- Davidson, R. R. (1970). On extending the Bradley–Terry model to accommodate ties. *JASA*.
- Houlsby, N. et al. (2011). [Bayesian active learning for classification and preference learning](https://arxiv.org/abs/1112.5745).
- Saha, A. & Gopalan, A. (2019). [Active ranking with subset-wise preferences](https://arxiv.org/abs/1810.10321).
- Maystre, L. & Grossglauser, M. (2017). [Just sort it! A simple and effective approach to active preference learning](https://proceedings.mlr.press/v70/maystre17a.html).
