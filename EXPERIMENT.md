# Experiment

This is how we find out whether rankify works, before we trust it or build more on it. There are two parts: a simulated benchmark, where we know the true ranking, and a human pilot, where we measure what simulation can't.

## Questions

1. Does the planner reach each mode's target in less time than the baselines? (G1, G2)
2. Do mixed round types save time over pairs only? (G3)
3. Is it instant? (G4)
4. Are Confidence and Could be calibrated? (G5, G6)
5. Is the rounds-left forecast honest? (G7)
6. When a mode stops, is the ranking as accurate as the mode promises? (G8)
7. Is it reproducible, and is the math correct? (G9, G10)
8. Does it hold up when a judge breaks the model's assumptions?

Goal numbers refer to [GOALS.md](GOALS.md).

## The standing benchmark: `rankify bench`

Every change to rankify is compared against rating systems built for human judges with `rankify bench`, and the report is saved in `experiments/`. The benchmark runs each method the way a person would use it:

1. Draw hidden scores for N items. The shape is a few clear favourites and a crowded middle (a Student-t distribution with 3 degrees of freedom).
2. Make a fresh list with `rankify new --method <method>`.
3. Each round, `rankify next --json` asks a question. A simulated judge compares the two items' hidden scores and answers with `rankify answer --round` or `--cant-decide`. Then `rankify show --json` records the method's current ranking.
4. Stop at the round budget, or when the method says it has nothing left to ask (exit code 3).

Every method sees the same hidden lists. The calls run in-process through the real CLI code. A separate sample times real `rankify` subprocesses.

**The methods.** The main comparison is with rating systems built for human judges: `elo`, `elo-close` (Elo with pairs of close ratings), `glicko2`, `trueskill`, `openskill` and `arena` (random pairs with a Bradley–Terry fit, the way Chatbot Arena works). Two sorts run as reference lines only: `just-sort-it` and `insertion-sort`. Sorting assumes a judge who answers the same way every time, and people don't, so the sorts show the floor for a perfect judge rather than a fair competitor.

**The judges.**

- **human**, the headline. It behaves the way the research says people do. Perceived quality carries noise, so close items get confused (Thurstone 1927). The noise grows with fatigue. It leans toward the item shown first. It sometimes answers at random (lapses; Wichmann & Hill 2001). It says "can't decide" on near-ties. It takes longer on close calls (the distance effect; Moyer & Landauer 1967). Every setting is a guess until a real session calibrates it (Part 2).
- **perfect**, a sanity check. It is always right.
- **noisy**, optional. It uses Bradley–Terry noise only, which is the model rankify itself assumes.

Swaps between near-ties don't count as errors. A near-tie is a pair the human judge gets right less than 55% of the time.

The report measures:

- rounds and human minutes to reach Quick, Stable and Exact. These use the same definitions as the full grid below, and the minutes come from the judge's simulated answer times.
- Kendall τ against the hidden scores as rounds go by
- wasted questions: answers that already followed from earlier answers, and exact repeats
- Confidence calibration and Could be coverage, for methods that report them
- whether the ranking changes when the same answers come in a different order
- milliseconds per CLI call
- which requirements from the proposal each method meets, with unbuilt rankify features shown as gaps

```sh
uv run rankify bench --items 10,20 --runs 20 --report experiments/<date>-<name>.md
```

The full grid in Part 1 extends this with more judges, sizes and seeds.

## Part 1: Simulated benchmark

### Ground truth and simulated judges

Each run draws true scores for N items from a normal distribution. Its spread sets how hard the list is: a small spread means many items are close together.

A simulated judge answers each round by drawing from a model applied to the true scores. We test nine kinds:

- **Sharp, Normal and Fuzzy** answer exactly as our model assumes, with decreasing consistency. Neighbouring items in a 20-item list are told apart correctly about 90%, 75% and 60% of the time.
- **Careless** is Normal, but 5% of answers are random. This tests that an answer is evidence, not a verdict.
- **Biased** is Normal, plus a bonus for whatever is shown first. This tests position-bias correction.
- **Thurstone** uses a slightly different noise curve (probit in place of logistic). Here the model is wrong in a small way.
- **Similar items** has pairs of near-identical items that split "pick the best" votes. Here the model is wrong in a known way.
- **Tired** gets 1% noisier every round, like a long session.
- **Perfect** is always right and never ties. It is a sanity check against sorting theory.

The pilot (Part 2) checks which of these real people resemble.

### Simulated time

Each round costs simulated seconds. A pair takes 2 s, plus up to 3 s more on a close call (the distance effect). Ordering k items takes one such call per neighbour in the judge's order. Picking the best of k takes one call between the best two, plus 1 s per other item. Every time is multiplied by random noise (lognormal, spread 0.25). These are guesses. So that no conclusion hinges on them, every comparison of round types is repeated with pick and rank rounds taking half as long, and then twice as long (`bench --set-time-scale 0.5` and `2`).

The planner doesn't know these times. It starts from its own guesses (DESIGN.md) and switches to the judge's measured times as answers come in.

Fatigue grows with the calls made, not the rounds: ordering k items counts as k − 1 calls.

### Methods compared

- **Elo, random pairs** (K = 32): what we want to replace.
- **Elo, close pairs**: K = 32, matching the closest current ratings. A fairer, stronger Elo.
- **Random pairs with our fit**: separates the gain from fitting from the gain from choosing.
- **openskill**: online Plackett–Luce ratings with closest-rating matching. A modern online method.
- **Merge-insertion sort** (Ford–Johnson), where every answer is final: the minimum number of pairs for a perfect judge.
- **Just Sort It**: repeated quicksort with a Bradley–Terry fit. The strong baseline.
- **Planner, pairs only**: isolates the planner.
- **Planner, full**: pairs, picks and orderings. The full design.
- **Planner, closest to 50/50**: picks the round closest to 50/50 in place of using BALD. Checks that BALD matters.
- **Planner, per round**: maximizes gain per round in place of gain per second. Checks that the time model matters.

### The grid

We run every combination of:

- list sizes of 10, 20, 50 and 100 items
- all nine judges
- all three modes
- 100 seeds per combination to start, with more wherever the 95% interval of a difference is wider than ±10%

Runs are paired. For a given combination and seed, every method gets the same true scores and the same stream of random noise. This removes most of the run-to-run variation from the comparison.

### Stopping, fairly

Baselines like Elo have no confidence target, so they can't decide when to stop. We give them an advantage. An oracle that knows the truth stops each baseline at the first round where its ranking meets the mode's accuracy definition, provided it stays there for the next 10 rounds. rankify gets no oracle. It stops on its own rule, and then we check its accuracy. If rankify wins under these rules, the win is real.

What "accurate" means for each mode, judged against the true scores:

- **Quick**: the true #1 is at #1, and the true top 3 are in the top 3.
- **Stable**: the top part is in exactly the right order, and no other item is more than one tier from its true tier.
- **Exact**: every neighbour pair is in the right order, except true near-ties (closer than the tie margin).

### What we measure

The main measure is **simulated seconds to reach the target**. Alongside it we track:

- rounds to reach the target
- accuracy when rankify stops
- accuracy over a whole session against time spent, which shows whether a method is useful if you stop early
- calibration: Confidence compared with how often the order is really right (a reliability plot, the expected calibration error, and the Brier score)
- how often Could be contains the true rank
- forecast coverage and median error, checked every 5 rounds
- wasted rounds: rounds whose answer the model predicted with more than 95% probability
- time to save, refit, plan and forecast: the median, the 95th percentile, and the maximum

### Sanity checks first

Run these in order before the full grid. If one fails, fix the cause before going further.

1. **The fit matches `choix`.** Our scores match `choix`'s regularized fits on the same data (G10).
2. **Order doesn't matter.** Shuffling the rounds leaves every score unchanged (G9).
3. **Perfect judge, small list.** With 5 to 10 items and a perfect judge, the pairs-only planner needs no more than 1.5 times the Ford–Johnson number of pairs. If it needs more, the model is too cautious about noise.
4. **Replay.** The same seed and answers give the same rounds.
5. **Read one run.** `rankify sim --trace` on one 10-item run prints every round, the candidates and the scores. A person reads the trace and checks that each choice makes sense.

### Writing the plan down first

Before the full grid runs, we commit the targets in [GOALS.md](GOALS.md), the grid and methods above, and the analysis: paired differences in seconds-to-target, reported as medians with bootstrap 95% intervals. Any result we didn't plan for is reported as exploratory, not as a win.

## Part 2: Calibration and pilot

Simulation can't tell us how long people really take, how consistent they are, or whether the result feels right. Two kinds of real session answer that.

### Calibration session

One person ranks one real list of about 15 items with `rankify play`, on a list made with `--calibrate`. About 15% of rounds repeat an earlier pair with the sides swapped. `rankify calibrate` then fits the benchmark's human judge to the answers. It converts our fitted scores to the judge's normal-noise units, and estimates each setting by maximum likelihood or least squares.

The direct estimates are biased. The gap between two items is itself estimated, and that noise weakens every relationship measured against it (the errors-in-variables problem; Fuller 1987). A parametric bootstrap corrects this (Efron & Tibshirani 1993): it simulates sessions like the person's own, measures the estimator's bias on them, and subtracts it. The correction is applied only where a recovery check showed that it helps: tie settings, close-call timing and list difficulty.

**Recovery check (2026-10-12).** A simulated judge with known settings answered six sessions of 120 answers and six of 400. These are the medians recovered:

| Setting | True | 120 answers | 400 answers |
|---|---|---|---|
| Answer time, easy pairs | 2.0 s | 1.9 s | 2.0 s |
| List difficulty (spread) | 1.5 | 1.44 (0.6–2.6) | 1.28 (0.8–3.8) |
| "Can't decide" peak | 30% | 17% | 29% |
| Close-call time width | 0.6 | not recovered | 0.64 |
| Fatigue per round | 0.3% | not recovered | 0.2% |
| Lean toward the first item | 0.15 | not recovered | not recovered |
| Random slips | 3% | not recovered | not recovered |

So a profile says which settings it measured, and the benchmark uses only those:

- About 60 answers measure answer time on easy pairs, list difficulty and the "can't decide" rate.
- About 300 answers add close-call timing, tie width and fatigue.
- The lean toward the first item and random slips keep the guesses at any length we tested.

Several sittings on the same list add up.

### Pilot

The pilot runs real sessions on three lists: about 20 places to travel to, about 10 products to buy, and about 15 restaurants from the last month.

During those sessions we record:

- **seconds per round type and size**, which rankify logs anyway
- **self-consistency**, using hidden repeat rounds (5% of rounds, during the pilot only)
- **position bias**, from the fitted model
- **whether the result feels right**: after each session, "how many items would you move?", plus the moves you actually make in a final edit
- **forecast honesty**: the predicted rounds left against the actual number

The measured times replace the timing guesses. Then we rerun the Part 1 comparison of round types with the real numbers.

## Making it work

**Runs are reproducible.** `rankify sim` reads a config file, runs the grid, and writes every run to SQLite: the commit hash, the engine version, the seeds, each round and each measure. A script generates plots and tables from that database. They are never made by hand.

```sh
rankify sim --config experiments/grid-v1.toml --out experiments/grid-v1.db
rankify sim --items 10 --judge normal --method planner-full --seed 7 --trace
```

**Compute budget.** The full grid should finish in under an hour on a laptop, using all cores. If it doesn't, first cut seeds for the 100-item lists, then profile.

**What could mislead us, and what we do about it:**

- *The simulated judges follow our own model, which favours our planner.* The Careless, Biased, Thurstone, Similar items and Tired judges break the model on purpose.
- *The timing model is a guess.* We rerun at half and double the times, and the pilot replaces the guesses.
- *Real taste may not follow a normal distribution.* We repeat the main comparison with a heavy-tailed spread: a few clear favourites and a long, similar middle.
- *The pilot has one judge.* We treat its numbers as a first estimate, and check them again once there are more judges.

## Results

Results go in `experiments/`, one report per run, linked from here.

- [2026-10-11: Phase 1 against Elo and others](experiments/2026-10-11-phase1-vs-elo.md). This report used only the perfect and Bradley–Terry judges, which turned out to favour sorting. Replaced by the next entry.
- [2026-10-12: Phase 1 against rating systems, with a human judge](experiments/2026-10-12-human-judge.md). rankify still asks random pairs.
  - Against the rating systems, rankify is mid-pack to slightly ahead. On 10 items it reached Quick in 62 rounds (2.5 min); Elo needed 64 and TrueSkill 78. On 20 items it beat Elo and Arena on Quick but trailed Glicko-2 (259 rounds against 126).
  - No method reached Exact on 20 items with the human judge.
  - About 90% of questions in every random-pair method were already answered by earlier answers.
  - With the human judge, Confidence is calibrated (error 0.017–0.032), and Could be is slightly too wide (96–98%). The earlier "too cautious" result came from the unrealistic judges.
  - Insertion sort collapses with a human judge.
- [2026-10-12: Phase 2 planner, v1](experiments/2026-10-12-phase2-planner-v1.md): order information, learned prior width, and stopping rules.
  - With the perfect judge, rankify is far ahead. On 20 items it reached Quick in 29 rounds (Elo 191, Glicko-2 89) and Exact in 80 (Elo never). When it stopped, its target held in 59 of 60 lists.
  - With the human judge, it stopped too early. On 10 items it reached Quick in 34 rounds, 57% of Elo's time, but in only 12 of 20 lists. On 20 items it got the top 3 right in only 5 of 20.
  - A diagnosis on 10 lists found the cause. On crowded lists the learned width collapsed, the model decided everything was nearly tied, and a one-answer "worth asking" test stopped the session. In one list, the clearly best item lost its first comparison to a slip and was never asked about again.
- **Tuning between v1 and v2** (seeds 30000+, which the benchmark never uses; 10 lists per setting, human judge). After adding first looks and the Could be check, we compared the floors 0.05, 0.1 and 0.2 bits over the next 8 answers.
  - 0.1 was the best balance. On 20-item Quick it reached the target in 10 of 10 lists, in 25% of Elo's time, and was right at every stop. On 10-item Stable it took 71% of Elo's time.
  - 0.2 stopped far too early. 0.05 ran much longer for little gain.
  - On 10-item Quick, rankify needed 130% of Elo's time on these lists. With only 45 pairs, random pairs cover a short list quickly.
- [2026-10-12: Phase 2 planner, v2](experiments/2026-10-12-phase2-planner-v2.md): first looks, the Could be check, and the 8-answer floor. 880 runs, none failed.
  - **20 items, human judge, Quick:** 69 rounds (3.1 min). Elo needed 315 (13.3 min) and Just Sort It 141. That is 23% of Elo's time (G1 met) and 52% of Just Sort It's (G2 met). rankify reached the target in 11 of 20 lists, Elo in 12.
  - **10 items, human judge:** Quick took 39 rounds (66% of Elo's time, 76% of Just Sort It's) and Stable took 73 (67% of Elo's, 95% of Just Sort It's). G1 is not met on 10 items. G2 is met for Quick but not for Stable. rankify is the only method to reach Exact in most 10-item lists (11 of 20).
  - **20 items, Stable and Exact:** no method reached them in most lists.
  - **Stopping:** when rankify stopped, its target held in 14 of 20 lists for both Quick and Stable on 10 items, but only 9 of 20 for Quick on 20 items. On crowded lists it stops with "nothing worth asking" while near-ties at #3–#4 that a person gets right 55–60% of the time remain unresolved.
  - **Perfect judge:** 20 items took 40, 68 and 81 rounds to Quick, Stable and Exact. Elo took 191, 374 and never. rankify was right at every stop (60 of 60).
  - **Calibration:** error 0.038–0.049 (G5 met). Could be covered 90–98% with the human judge (G6 met on 20 items, slightly too wide on 10).
  - **Same answers in a different order:** rankify's #1 never changed (0 of 80). Elo's changed in 9 of 80.
- **Phase 3 tuning** (seeds 40000+ and 50000+, which the benchmark never uses; 12 lists per setting, human judge). Mixed rounds against pairs only.
  - The first mixed planner summed the information over every pair in a set. It chose orderings for about 90% of rounds and was slower than pairs for Quick: 2.8 times the time on 10 items and 1.85 times on 20, as the median of paired lists.
  - Posterior draws showed why. For five items of unknown order, the sum is 1.87 bits, while the exact information about their order is 0.99. Counting only neighbour pairs gives 0.75, within 25% and on the low side, and is exact for a pair. The planner now counts neighbours.
  - With neighbours counted, mixed rounds were still no faster than pairs on these lists.
  - The stopping rules were checked with judges that drop one human trait at a time (no lapses, no fatigue, or neither) and with the model's own judge. Confidence stayed calibrated (error 0.02–0.07). Early stops come from the per-pair stopping rules, not from overconfidence: even the model's own judge met the whole-order Exact target at only 1 of 8 stops.
- [2026-10-12: Phase 3, mixed rounds](experiments/2026-10-12-phase3-mixed-rounds.md), with pick and rank times [halved](experiments/2026-10-12-phase3-set-time-half.md) and [doubled](experiments/2026-10-12-phase3-set-time-double.md). 1,120 runs, none failed. In these reports `rankify` is the mixed planner and `rankify-pairs` is what ships.
  - **G3 is not met.** Mixed rounds' time as a share of pairs only, with the guessed times: 10-item Quick 74%, 10-item Stable 121%, 20-item Quick 108%. At half the time they are 33%, 75% and 45%. At twice the time they are 158%, 139%, and 20-item Quick is not reached in most lists. Pairs stay the default.
  - **Pairs only (as shipped):** 10-item Quick took 64% of Elo's time and 75% of Just Sort It's. 10-item Stable took 66% and 94%. 20-item Quick took 26% and 57%. These are close to the Phase 2 v2 numbers.
  - **Stopping:** on 10 items, mixed rounds stopped sooner (Quick 3.6 min against 4.0, Stable 5.1 against 5.9), and the true #1 was on top at every Quick stop (20 of 20; pairs 17 of 20). On 20 items they stopped a little later. Exact stopped with 88% of neighbour pairs right on 10 items and 78% on 20, short of G8's 95%. Pairs only reached 94% on 10 items, and on 20 items it never stopped in Exact.
  - **Calibration:** error 0.041–0.047 for mixed rounds and 0.043–0.048 for pairs (G5 met). The #1 never changed when answers were replayed in another order (0 of 80 for both).
- **Phase 4 forecast checks** (seeds 70000+, which the benchmark never uses; 5–6 lists per setting, human judge).
  - The first forecast planned pairs without weighting them by the mode. In Quick it spread questions over every item still in play and never stopped: it said about twice the real rounds left.
  - Weighting by a normal approximation of each rank broke differently. That approximation treats "j is above i" as independent for every j, so ranks look far too certain early on, and the forecast said "0 rounds left" right after first looks.
  - With posterior draws instead, the range held 61% of the time on 10-item Quick and 100% on 10-item Stable.
- [2026-10-12: Phase 4, rounds left](experiments/2026-10-12-phase4-forecast.md). 1,120 runs, none failed. The 640 baseline runs were reused from Phase 3, because their code didn't change.
  - **G7, human judge, pairs as shipped:** the range held 78% (Quick) and 89% (Stable) on 20 items, and 67% and 68% on 10 items. The median was off by 14–22%. Exact: 32% on 10 items, and unscorable on 20.
  - **G7 fails** on mixed lists (the forecast plans pairs only: medians off by 130–200%) and with the perfect judge (forecasts too long early on: medians off by 80–190%).
  - Rankings, calibration and every other number match the Phase 3 benchmark exactly; the forecast doesn't change which rounds are asked.
- **Forecast follow-up checks** (seeds 70000+; 6–10 lists per setting, human judge). Because the forecast never changes which rounds are asked, session states were saved once at each forecast point, and forecast variants were scored on them with a fixed 24 simulations.
  - Simulating picks and orderings took the mixed-list median error from 98–197% to 19–46%. The old forecast had run long because it asked pairs only.
  - Even so, mixed forecasts ran 20–59% high at round 0. With a judge who answers exactly as the model assumes and no habits, the overshoot stayed, so the cause was not the judge.
  - The forecast's planner, given the same state, picks the same kind of round as the real planner 85% of the time. Along simulated sessions, the real planner would ask pairs in 21% of rounds and the forecast's planner in 25–28%; real sessions ask 8–16%. Growing sets from two seed pairs instead of one changed nothing that mattered, at twice the cost.
  - The closed-form updates track full refits of the same 3–30 answers. With one Newton step per answer, the scores' spread came within 3–9% for orderings and picks, and the variances within 13%. A code review then found that one step overshoots after a surprising answer to an unsure fit (a "can't decide" could swap the two items), so each update now finds the mode of the shown items: spread within 0–6%, variances within 9%, and exact for one answer from the prior.
  - The prior width dips from 1.5 to about 1.0 after ten answers and climbs to 1.3–1.75 later. Drawing it per simulation and redoing the fit for it lifted the ranges (held 76–88% on mixed lists, from 52–76%) without moving the median much. Forcing the width to at least 1.5 made forecasts worse.
  - Slips (3% random answers) made forecasts run longer than reality: with them off, the mixed-list median error dropped from 17–35% to 17–27%. The fit already narrows its scores to explain the upsets it has seen.
  - The remaining overshoot comes from answer times: real sessions replace guessed times with measured ones, and orderings got cheaper than guessed. The simulation keeps the times known when it starts.
- [2026-10-12: forecast for mixed lists](experiments/2026-10-12-forecast-mixed.md). 1,120 runs, none failed. The 640 baseline runs were reused.
  - **G7, human judge:** met for pairs in Quick and Stable at both sizes (range held 76–89%, median off 14–24%) and for mixed Stable on 20 items (77%, 25%); mixed Stable on 10 items held 91%, just over the band. Not met for mixed Quick (median off 41–42%), mixed Exact (range held 53–62%) or pairs Exact (43% on 10 items, unscorable on 20).
  - **Perfect judge:** still fails.
  - Apart from forecasts and timings, every rankify run matches the Phase 4 benchmark exactly.
