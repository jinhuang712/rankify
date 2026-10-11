# Experiment

This is how we find out whether rankify works, before we trust it or build more on it. The experiment has two parts: a simulated benchmark, where we know the true ranking, and a human pilot, where we measure what simulation can't.

## Questions

| # | Question | Linked goals |
|---|---|---|
| Q1 | Does the planner reach each mode's target in less time than the baselines? | G1, G2 |
| Q2 | Do mixed round types save time compared with pairs only? | G3 |
| Q3 | Are Confidence and Could be calibrated? | G4, G5 |
| Q4 | Is the rounds-left forecast honest? | G6 |
| Q5 | Is it instant? | G7 |
| Q6 | Is it reproducible and mathematically correct? | G8, G9 |
| Q7 | When a mode stops, is the ranking as accurate as the mode promises? | G10 |
| Q8 | Does it survive judges that break the model's assumptions? | All |

## Part 1: Simulated benchmark

### Ground truth

Each run draws true scores for N items from `Normal(0, s²)`. The spread `s` sets how hard the list is: a small spread means many items are close.

### Simulated judges

A simulated judge answers each round by drawing from a model applied to the true scores.

| Judge | How it answers | Why we test it |
|---|---|---|
| Sharp | Plackett–Luce with large `s` (neighbours are easy to tell apart) | Best case |
| Normal | Plackett–Luce with medium `s` | Main case |
| Fuzzy | Plackett–Luce with small `s` | Many close calls |
| Careless | Normal, but 5% of answers are random | Principle 3: an answer is evidence, not fact |
| Biased | Normal, plus a bonus for whatever is shown first | Principle 9: control bias |
| Thurstone | Normal-curve (probit) noise in place of logistic | The model is wrong in a small way |
| Similar items | Pairs of near-identical items split "pick the best" votes | The model is wrong in a known way |
| Tired | Noise grows by 1% per round | Long sessions |
| Perfect | Always right, never ties | Sanity check against sorting theory |

Exact values of `s` are set so that neighbouring items at N = 20 are told apart correctly about 90% (sharp), 75% (normal) and 60% (fuzzy) of the time. The pilot (Part 2) checks whether real people look like any of these.

### Simulated time

Every round costs simulated seconds from the timing model in [DESIGN.md](DESIGN.md#planner): `pair` 3 s, `pick` of 4: 5 s, `rank` 3: 6 s, `rank` 4: 9 s, `rank` 5: 13 s. These are guesses. To keep the result from hinging on them, every comparison of round types is repeated with multi-item rounds costing half and double those times.

### Methods compared

| Method | What it is | Why it is here |
|---|---|---|
| Elo, random pairs | K = 32, random pairs | What we want to replace |
| Elo, close pairs | K = 32, pairs with the closest current ratings | A fairer, stronger Elo |
| Random pairs + our fit | Random pairs, scores fitted all at once | Separates the gain from fitting from the gain from choosing |
| openskill | Online Plackett–Luce ratings, closest-rating matching | A modern online rating method |
| Merge-insertion sort | Ford–Johnson sort, every answer final | The pair-count floor for a perfect judge |
| Just Sort It | Repeated quicksort with a Bradley–Terry fit | The strong baseline |
| Planner, pairs only | Our planner limited to pairs | Isolates the planner |
| Planner, full | Our planner with pair, pick and rank | The full design |
| Planner, uncertainty only | Full planner, but picks the round closest to 50/50 in place of BALD | Checks that BALD matters |
| Planner, no time cost | Full planner, maximizing gain per round in place of gain per second | Checks that the time model matters |

### Grid

| Factor | Values |
|---|---|
| Items N | 10, 20, 50, 100 |
| Judge | All nine judges above |
| Mode | Quick, Stable, Exact |
| Seeds | 100 per cell to start. More where the 95% interval of a difference is wider than ±10%. |

Runs are paired: in a given cell and seed, every method gets the same true scores and the same random noise stream. This removes most of the run-to-run variation from the comparison.

### Stopping, fairly

Baselines like Elo have no confidence target, so they can't decide when to stop. We give them an advantage: an oracle that knows the truth stops each baseline at the first round where its ranking meets the mode's accuracy definition and stays there for 10 more rounds. rankify gets no oracle. It stops on its own rule, and we then check its accuracy. If rankify wins under these rules, the win is real.

**Accuracy definitions** (against the true scores):

| Mode | Accurate means |
|---|---|
| Quick | True #1 is at #1, and the true top 3 are in the top 3 |
| Stable | Top K in exactly the right order, and no item more than one tier away from its true tier |
| Exact | Every neighbour pair in the right order, except true near-ties (closer than the tie margin) |

### Metrics

| Metric | Answers |
|---|---|
| Simulated seconds to target (main metric) | Q1, Q2 |
| Rounds to target | Q1, Q2 |
| Accuracy at stop | Q7 |
| Accuracy against seconds, over a whole session (area under the curve) | Whether a method is useful if stopped early |
| Calibration: Confidence against actual frequency (reliability plot, expected calibration error, Brier score) | Q3 |
| Could be coverage: share of items whose true rank falls in the range | Q3 |
| Forecast coverage and median error, checked every 5 rounds | Q4 |
| Wasted rounds: rounds whose answer the model predicted with > 95% probability | Principle 4 |
| Latency of save, refit, plan and forecast: median, 95th percentile, max | Q5 |

### Sanity checks, before the full grid

Run these first, in order. If one fails, fix the cause before going further.

1. **Fit matches `choix`**: our scores match `choix`'s regularized fits on the same data (G9).
2. **Order doesn't matter**: shuffling rounds leaves every score unchanged (G8).
3. **Perfect judge, small list**: with N = 5 to 10 and a perfect judge, the pairs-only planner needs no more than 1.5 times the Ford–Johnson pair count. If it needs more, the noise model is too cautious.
4. **Replay**: the same seed and answers give the same rounds.
5. **Single-run trace**: `rankify sim --trace` on one N = 10 run prints every round, the candidates and the scores. A person reads it and checks that each choice makes sense.

### Pre-registration

Before the full grid runs, we commit:

- the targets in [GOALS.md](GOALS.md)
- the grid and the methods above
- the analysis: paired differences in seconds-to-target, with medians and bootstrap 95% intervals

Results that we didn't plan are reported as exploratory, not as wins.

## Part 2: Human pilot

Simulation can't tell us how long people really take, how consistent they are, or whether the result feels right. So we run sessions on real lists:

- places to travel to (about 20 items)
- products to buy (about 10 items)
- restaurants from the last month (about 15 items)

| Measure | How |
|---|---|
| Seconds per round type and size | Logged in `rounds.ms` |
| Self-consistency | 5% hidden repeat rounds, during the pilot only |
| Position bias | Fitted `β` |
| Does the result feel right? | After each session: "How many items would you move?" and the actual moves made in a final edit |
| Forecast honesty | Predicted rounds left against actual, logged during real sessions |

The measured seconds replace the timing defaults. Then the Part 1 comparisons of round types are run again with the real numbers.

## Making it work

**Reproducible runs.** `rankify sim` reads a config file, runs the grid, and writes every run to SQLite, including the commit hash, the engine version, the seeds, each round, and each metric. Plots and tables are generated from that database by a script, never by hand.

```sh
rankify sim --config experiments/grid-v1.toml --out experiments/grid-v1.db
rankify sim --items 10 --judge normal --method planner-full --seed 7 --trace
```

**Compute budget.** The full grid should finish in under one hour on a laptop, using all cores. If it doesn't, cut seeds for N = 100 first, then profile.

**Threats to validity**

| Threat | What we do about it |
|---|---|
| Simulated judges follow our own model, which favours our planner | The Thurstone, Similar items, Careless, Biased and Tired judges break the model on purpose |
| The timing model is guessed | Sensitivity runs at half and double. The pilot replaces the guesses. |
| Ground truth from a normal distribution may not match real taste | Repeat the main comparison with a heavy-tailed spread (a few clear favourites, a long similar middle) |
| The pilot has one judge | Treat pilot numbers as a first estimate. Re-check once there are more judges. |

## Results

Results go in `experiments/` as databases, plots and a short write-up per run, linked from here. None yet.
