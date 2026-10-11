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

Each round costs simulated seconds. A pair costs 3 s, a pick of 4 costs 5 s, and ordering 3, 4 or 5 items costs 6, 9 or 13 s. These are guesses. So that no conclusion hinges on them, every comparison of round types is repeated with multi-item rounds costing half as much, and then twice as much.

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

## Part 2: Human pilot

Simulation can't tell us how long people really take, how consistent they are, or whether the result feels right. So we run real sessions on three lists: about 20 places to travel to, about 10 products to buy, and about 15 restaurants from the last month.

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

Results will go in `experiments/` as databases, plots and a short write-up per run, linked from here. There are none yet.
