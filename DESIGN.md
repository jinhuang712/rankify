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

- **"Can't decide" is a real answer.** For pairs we use Davidson's extension of Bradley–Terry, which models ties. In v1, "can't decide" in a pick or rank round is recorded but not used, and that set is not asked again.
- **Position bias is measured.** Each display slot gets a small fitted bonus, so a habit of choosing the first item doesn't leak into the scores.
- **Every score starts in the middle, with a wide range.** This gives the fit a single answer and keeps new or rarely seen items from jumping around. The width of that starting range is learned from how consistent the judge is, so a very consistent judge's answers count for more.

The model has two known limits. It assumes taste lies on one axis. It also assumes that adding a third option doesn't change the odds between two others. Similar items can break the second assumption, so a pick or rank round never shows two items the model already holds to be tied. That catches near-identical items once their scores have met. It can't see that two items are alike before the answers show it. The report flags answers the model can't explain, which is where either limit would show up.

## Fitting

After each round, the model is fitted to all answers at once. This is what makes the result independent of answer order, and it is the main difference from Elo, which updates one match at a time. An Elo update is one small step toward this same fit.

The fit starts from the previous scores, so one new answer needs only a few Newton steps. Each item's range comes from the curvature of the fit around its best value (the Laplace approximation). Score, Confidence and Could be all follow from the scores and their ranges. Two items that are confidently close become a confident tie, shown as `=`, and the planner stops asking about them.

**The prior width is learned.** Every score starts at Normal(0, σ²), and σ is learned from the answers (MacKay 1992). A consistent judge spreads items far apart, so σ grows and each answer counts for more. A judge who contradicts themself keeps σ narrow. The width maximizes the evidence, found by expectation-maximization over the Laplace posterior (Dempster, Laird & Rubin 1977), sped up by secant steps. Aitken's acceleration was tried first and failed to converge when the best width was far from the start. A weak prior on log σ, centred at 1.5, stops σ from collapsing on lists with few answers. Like the scores, σ depends only on the set of answers.

## Choosing the next round

The planner looks for the question that teaches the most about the **order** per second of your time, about the part of the ranking your mode cares about. A question is a pair. A list made with `new --rounds mixed` can also ask a pick ("which is best?") or an ordering ("put these in order") of 3 to 5 items. That is not the default, because in the Phase 3 benchmark it saved time on some targets and cost time on others (ROADMAP.md).

For each candidate pair, it estimates the mutual information between your answer and which of the two items is really better. This is in the spirit of BALD (Houlsby et al. 2011), but aimed at the order. Plain BALD measures information about the scores, so it kept asking pairs whose order was already settled, just to sharpen the size of their gap. The order measure is zero for pairs whose order is known. It is also zero for pairs already known to be tied, whose answer is a coin flip that teaches nothing.

Each pair's information is weighted by how much the pair matters for the mode: the chance, over posterior draws, that either item really belongs to the part the mode settles. That part is the top 3 for Quick, the top quarter for Stable (plus a smaller weight for tier boundaries), and everything for Exact. The weighted information is then divided by how long the pair is expected to take you. That estimate comes from your own answer times, which grow on close calls (Moyer & Landauer 1967), with a flat guess until there are 20 timed answers.

**Every item gets a first look.** Before the planner judges any item unimportant, every item gets at least two answers: the least-seen item goes against its most informative partner. Without this, an item that has barely been compared sits mid-ranking with a wide range and never looks like a contender. In one benchmark list, the clearly best item lost its first comparison to a slip and was never asked about again.

**Picks and orderings** are scored the same way, summed over the neighbour pairs they show: for each pair of items next to each other in the set's current order, how much the answer settles which of the two is better, times how much that pair matters for the mode. Only neighbours count because the rest of the order follows from them. A first version summed over every pair, which counted the same information about twice for an uncertain set of five, and it chose orderings for about 90% of rounds while being slower than pairs alone. Counting neighbours comes within about 25% of the exact information about the set's order, on the low side.

The exact value needs thousands of posterior draws per candidate, which is too slow between rounds. The planner uses a Gaussian shortcut instead. The answer's expected Fisher information shrinks the covariance of the shown items (a Laplace update), and each pair's uncertainty about its order shrinks with it. On test cases this stays within about 20% of the exact value. Candidates grow from the two best pairs, one item at a time up to 5, each time adding the item that adds the most. The best pairs are scored the same way, so every kind competes on one scale.

A pick or ordering's time starts as a guess, as a multiple of your typical pair: 1.33, 1.67 and 2 for picking from 3, 4 and 5 items, and 2, 3 and 4.33 for ordering them. After 8 timed answers of one kind and size, your own median replaces the guess. Stopping still looks at pairs only, by the same rules as before, so a list stops for the same reasons whichever kinds of round it asks.

The best candidate wins, and its display order is shuffled with the round's seed. The candidates the planner weighed are saved, so `rankify why` can explain the choice.

**Stopping.** The session stops when the mode's target is reached. It also stops when nothing is worth asking: even 8 more answers to the most useful pair would teach less than 0.1 bits about the order that matters. The test looks at several answers, not one, on purpose. A judge who gets a pair right 60% of the time teaches only about 0.03 bits per answer (1 − h(0.6)), but those bits add up. A one-answer test stopped far too early on crowded lists. The 0.1-bit threshold was tuned on hidden lists the benchmark never uses (EXPERIMENT.md).

Calibration lists (`--calibrate`) keep random pairs with swapped repeats. That is the design the calibration's bias correction simulates.

Multi-item rounds help only in some situations. Saha & Gopalan (2019) show that with noisy answers, "pick the best of k" is no faster than pairs, while ordering the top m items is about m times faster. So picks pay off mainly when one item clearly stands out, and orderings pay off when a few items are close. The planner doesn't need these as hard-coded rules. They fall out of the gain-per-second scoring. Whether the scoring gets them right is a question for the benchmark (goal G3).

## Modes

Each mode is a confidence target, not a fixed number of rounds.

- **Quick** stops when the winner is clear (90% Confidence over #2), the top 3 are fairly clear (80%), and no item below #3 could still be in the top 3 (its Could be range stays below). Everything else stays in rough tiers.
- **Stable** stops when the top of the list (about a quarter of it, at least 3 items) is in a confident order (90%), no item below could still reach it, and the rest falls into confident tiers.
- **Exact** stops when every neighbouring pair is in a confident order (95%) or is a confident tie.

In every mode, a confident tie (at least 90% likely to be within 30 Score points) counts as settled. The thresholds can be adjusted, and the benchmark will tune the defaults. `show` reports whether the list's mode has reached its target, and `next --mode` asks one session in another mode without changing the list.

## Rounds left

To estimate rounds left, rankify plays the rest of the session forward many times in simulation. Each time, it draws plausible "true" scores from the current fit, simulates your answers the way the model expects them, and runs a cheap version of the planner until it would stop. The spread of the round counts gives a range like "about 14 (10–19)": the median, and the 10th to 90th percentile.

The cheap planner keeps the real one's rules: first looks, pairs weighted by how much they matter for the mode, the mode's target, and the 8-answer floor. On a list with mixed rounds it also grows picks and orderings with the real planner's own code, and weighs them against pairs by information per second, using your times so far. The real planner grows sets from the two best pairs; the forecast grows them from the best one, which halves the time and changed the forecasts very little.

The simulated judge answers the way the model expects: Bradley–Terry for pairs, and Plackett–Luce for picks and orderings, drawn by adding Gumbel noise to each score and sorting (Yellott 1977). Three things come on top:

- **Can't decide:** at the rate the fit has learned for this list, from Davidson's tie weight.
- **Fatigue:** answers get noisier as a sitting goes on, by the benchmark's guess (0.3% per call, at most 1.6 times), relative to how tired you were, on average, in the answers the fit has seen. A pause of more than 30 minutes starts a new sitting, and the simulation goes on from where the current one is. One short list can't measure this, so it stays a guess until the pilot does.
- **Sharpness:** how much more decisive you are than the model expects. Before each answer rankify had an expectation for it, saved with the fit it asked from. A calibration slope of your last 200 answers against those expectations (Cox 1958), allowing for how unsure each expectation was, comes out near 1 for a judge the model describes well and higher for one who never contradicts themself. It is held near 1 until the answers clearly say otherwise.

Occasional random answers (lapses) were tried and left out. The fit already narrows its scores to explain the upsets it has seen, so simulating lapses on top counted them twice, and the forecasts ran long.

The fit learns how widely scores spread from your answers (the prior width), and early on it is unsure of it. On the benchmark's lists it dips from 1.5 to about 1.0 after ten answers and climbs back to 1.3–1.75 later. So each simulation first draws a width from what is known about it, and redoes the fit for that width with the same answers. Before any answers the width is only known to its hyperprior. Each item the answers pin down narrows it further, the way MacKay (1992) counts well-determined parameters. Without this the ranges held the real rounds left too rarely. The simulated fit then learns its width again from the simulated answers every 4 answers, with the real fit's EM step, so it moves as the real fit's does. Before that, a simulation that drew a very narrow width kept it as if it were known and stopped right after first looks, which gave fresh lists ranges like "72 (12–99)".

Refitting after every simulated answer would be far too slow. Instead each answer updates the fit's Gaussian in closed form. A pair answer takes the moment-matching step TrueSkill uses for a game (Herbrich, Minka & Graepel 2007). The logistic curve is matched by a probit curve with scale 1.702, and for a probit answer the step gives the exact posterior mean. A pick, an ordering or "can't decide" finds the posterior mode of the items shown with a few damped Newton steps, and takes their covariance from the answer's Fisher information there: a Laplace update, as in the real fit. The other items follow through their covariance with the items shown. From the prior this is exactly the full refit of the same answer. A single Newton step from the current mean was tried first; it overshot when an answer surprised a fit that was still unsure, and a "can't decide" could even swap the two items. Could be and each pair's weight come from 96 posterior draws, refreshed every 4 simulated answers. A first version estimated ranks with a normal approximation that treated "j is above i" as independent for every j. That made ranks far too certain early on, and the forecast said "0 rounds left" right after first looks.

A forecast takes up to about a second. Within its 0.8 s budget it runs about 10 to 60 simulations on a list of pairs (fewer on longer sessions), and about 6 to 25 on a mixed list, where each simulated round grows sets. A simulation stops at 50 rounds per item; Exact on 20 items with the benchmark's human judge took about 25 per item. On a large list a simulation can run out of time; it then counts only as "at least this many", and if that leaves the median unknown, the answer is "at least N rounds". In the terminal UI the forecast runs a few simulated rounds at a time between keypresses, and the header shows the previous estimate, marked "updating", until the new one is ready. A forecast is saved, keyed by the answer log, the items and the mode, and reused until one of them changes.

What the forecast can't see coming: your answer times. A mixed session measures how long you take for each kind and size of round, and as those times replace the guesses, the real planner's mix shifts. On the benchmark's judge, orderings turn out cheaper than guessed, so real sessions ask fewer pairs than the simulation does (8–16% against about 25–40%) and finish sooner. Given the times each session ended up measuring, 20-item mixed forecasts ran 3% long on Quick instead of 16%. Predicting set times from the first few timed answers did not help, because much of the shift comes from your pair time, which a mixed session measures last. Goal G7 measures how much all this matters (see ROADMAP.md).

A judge who never errs is the other known miss. Its forecasts run two to three times long, and even when told the judge is nearly perfect (a sharpness of 8), they still ran 33–97% long: with no contradictions, the real fit spreads the scores faster than the simulated fit does.

## Storage

All data lives in one local SQLite file.

The source of truth is a small set of tables: lists, items, judges and rounds. Each round records what was shown, in which order, the answer, how long it took, and its seed. Rounds are only ever added. An undo is a new round that cancels an earlier one. A removed item is hidden from the ranking, but its rounds stay in the fit, because they still say something about the other items.

Everything else is derived: fits (scores and ranges after each round), plans (what the planner considered), forecasts and logs. Each derived row records which engine version made it and which rounds it used. `rankify verify` rebuilds the latest fit from the answer log and checks that it matches; `rankify rebuild` replaces it with one made by the installed engine and drops saved forecasts. The fits made after each answer and the plans are kept as a record of what rankify believed and asked at the time; the rounds-left forecast reads them to learn how decisive the judge is. `rankify export` writes the list, its items and its rounds as JSON lines that stand on their own.

## Code layout

```text
rankify/
  engine/     the math; no I/O
  store/      SQLite; no math
  service.py  ties the engine to the store; everything else calls this
  cli/        commands (see cli/CLI.md)
  tui.py      the terminal UI (Textual)
  report.py   the agent report
  bench.py    the benchmark; the simulated judges are in engine/judge.py
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

Upsets are answers the final scores give less than a 10% chance. Slow decisions are answers that took more than twice the same judge's median for the same kind and size of round, once there are 5 of them (ordering five items always takes longer than a pair). A weak spot is a neighbour pair below the mode's confidence level (95% in Exact, 90% otherwise) whose two items never met in a round. Consistency compares how many of the judge's pairwise statements (a pick says the pick beat each other item; an ordering says each item beat every one below it) agree with the final ranking, against how many would if the model were exactly right. The report is `rankify report` in Markdown, or JSON with `--format json`.

An agent can also query the SQLite file directly.

## Speed

From answer to next round should take under 50 ms for lists of up to 200 items. That breaks down into about 5 ms to save, 10 ms to refit and 30 ms to plan. The forecast gets up to a second, in the background. Performance tests enforce these targets.

Measured on 2026-10-12 (Phase 4), for 200 items, on a list with mixed rounds (the slower kind):

- Saving an answer takes 0.02 ms, and a warm refit with a fixed width 3.5 ms.
- Answer to next round takes 31 ms at the median and 38 ms at the 95th percentile. Asking the next round reuses the fit the answer just made, instead of fitting twice.
- The forecast stays within its budget of about a second.
- In the terminal UI on 20 items, the next round is drawn 3.5 ms after the answer key, and a key reaches the UI within 1 ms while a forecast runs.
- On a 20-item mixed list (measured after the forecast follow-ups), the next round is drawn 25 ms after the answer key (p95 31 ms), most of it planning sets, and a key still reaches the UI within 1 ms. A forecast on a mixed list pauses after every simulated round. Headless tests that time a key to the next round read about 0.9 s, but that is Textual's test pilot waiting up to a second for the process to go idle.
- The expected information of an ordering is summed stage by stage, with each stage's choice probabilities laid out by item: the same numbers to 1e-15 as a dense sum over every order, and 2.3–2.8 times faster.

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
