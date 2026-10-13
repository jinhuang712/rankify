# Benchmark: rankify against rating systems for human judges

- Date: 2026-10-12 11:54 UTC
- Code: commit fef1db1 + uncommitted changes, engine 0.3.0
- Setup: 50 items; judges: human, normal; 10 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 1114 s.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify as shipped (pairs); rankify-mixed (the same with `new --rounds mixed`, which also asks picks and rankings of 3 to 5 items); when run, two planner variants that check rankify's design (rankify-closest asks the relevant pair closest to 50/50, rankify-per-round counts information per round, not per second; both stop by rankify's rules); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and three sorts as reference lines only (Just Sort It, binary insertion, and Ford–Johnson merge insertion, which needs the fewest comparisons). The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes, as accurate as the human judge. **sharp**, **normal**, **fuzzy**: the model rankify assumes, telling neighbours on a 20-item list apart 90%, 75% and 60% of the time. The rest are normal with one twist: **careless** answers 5% at random; **biased** favours the item shown first (60% between equals); **thurstone** has normal-curve noise; **similar** gives a quarter of the items a near-identical twin, and twins shown together in a pick or ordering split one option's chance (Debreu 1960); **tired** gets 1% noisier every round.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 71% | 4% | 3.6 |
| normal | 86% | 0% | 3.6 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 50 items: neighbours told apart 53% of the time (median), 68% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 50 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | — (1/10) | — (0/10) | — (0/10) |
| **rankify-mixed** | — (5/10) | — (0/10) | — (0/10) |
| elo | — (5/10) | — (0/10) | — (0/10) |
| glicko2 | — (5/10) | — (0/10) | — (0/10) |
| just-sort-it (reference) | 444 · 20.2 min (8/10) | — (0/10) | — (0/10) |
| ford-johnson (reference) | — (2/10) | — (0/10) | — (0/10) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 10/10 | 1/10 | #1 right in 7/10 | 90 | 3.8 |
| stable | 10/10 | 0/10 | 69% of pairs right | 461 | 22.0 |
| exact | 0/10 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 10/10 | 5/10 | #1 right in 10/10 | 48 | 6.2 |
| stable | 10/10 | 0/10 | 74% of pairs right | 160 | 25.5 |
| exact | 10/10 | 0/10 | 66% of pairs right | 426 | 63.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick n/a, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick n/a, stable n/a, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick n/a, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.3 s | 0% | 0% |
| rankify | stable | 100% · 2.6 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 6% · 3.0 s | 4% · 3.8 s | 90% · 8.0 s |
| rankify-mixed | stable | 11% · 2.9 s | 2% · 4.3 s | 87% · 9.4 s |
| rankify-mixed | exact | 25% · 3.3 s | 1% · 4.0 s | 75% · 10.0 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 41 | 76% | 25% | 0 | 0 |
| rankify | stable | 50 | 84% | 11% | 0 | 0 |
| rankify | exact | 0 | — | — | 0 | 50 |
| rankify-mixed | quick | 35 | 86% | 20% | 0 | 0 |
| rankify-mixed | stable | 50 | 56% | 27% | 0 | 0 |
| rankify-mixed | exact | 50 | 66% | 14% | 14 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.19 | 0.32 | 0.46 | 0.53 | 0.69 | 0.78 |
| **rankify-mixed** | 0.39 | 0.56 | 0.70 | 0.77 | 0.84 | 0.86 |
| elo | 0.20 | 0.31 | 0.42 | 0.52 | 0.61 | 0.70 |
| glicko2 | 0.20 | 0.31 | 0.43 | 0.53 | 0.61 | 0.71 |
| just-sort-it (reference) | 0.16 | 0.23 | 0.31 | 0.45 | 0.60 | 0.72 |
| ford-johnson (reference) | 0.19 | 0.30 | 0.42 | 0.47 | 0.66 | 0.67 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 85% | 50% | 0/10 |
| **rankify-mixed** | 91% | 13% | 10/10 |
| elo | 89% | 31% | 0/10 |
| glicko2 | 89% | 31% | 0/10 |
| just-sort-it (reference) | 77% | 29% | 0/10 |
| ford-johnson (reference) | 0% | 0% | 10/10 |

## 50 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | — (4/10) | 292 · 16.1 min (9/10) | 788 · 51.5 min (10/10) |
| **rankify-mixed** | 31 · 4.1 min (10/10) | 69 · 10.6 min (10/10) | 282 · 33.4 min (10/10) |
| elo | — (4/10) | — (0/10) | — (0/10) |
| glicko2 | — (3/10) | — (0/10) | — (0/10) |
| just-sort-it (reference) | 284 · 14.2 min (10/10) | 576 · 29.4 min (8/10) | — (1/10) |
| ford-johnson (reference) | 102 · 5.1 min (10/10) | — (2/10) | — (0/10) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 10/10 | 4/10 | #1 right in 10/10 | 96 | 3.8 |
| stable | 10/10 | 7/10 | 97% of pairs right | 446 | 25.9 |
| exact | 0/10 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 10/10 | 10/10 | #1 right in 10/10 | 43 | 5.9 |
| stable | 10/10 | 10/10 | 100% of pairs right | 160 | 23.4 |
| exact | 10/10 | 7/10 | 99% of pairs right | 675 | 65.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick n/a, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick n/a, stable 55%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick n/a, stable 66%, exact 65%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.3 s | 0% | 0% |
| rankify | stable | 100% · 3.2 s | 0% | 0% |
| rankify | exact | 100% · 3.9 s | 0% | 0% |
| rankify-mixed | quick | 5% · 3.3 s | 5% · 3.9 s | 90% · 8.2 s |
| rankify-mixed | stable | 25% · 4.2 s | 3% · 3.9 s | 72% · 10.1 s |
| rankify-mixed | exact | 73% · 4.4 s | 1% · 5.2 s | 25% · 10.0 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 43 | 86% | 11% | 0 | 0 |
| rankify | stable | 50 | 80% | 13% | 0 | 0 |
| rankify | exact | 0 | — | — | 0 | 50 |
| rankify-mixed | quick | 32 | 88% | 23% | 0 | 0 |
| rankify-mixed | stable | 50 | 68% | 22% | 0 | 0 |
| rankify-mixed | exact | 50 | 92% | 28% | 22 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.22 | 0.35 | 0.55 | 0.73 | 0.88 | 0.95 |
| **rankify-mixed** | 0.48 | 0.71 | 0.90 | 0.94 | 0.96 | 0.97 |
| elo | 0.20 | 0.36 | 0.48 | 0.60 | 0.70 | 0.81 |
| glicko2 | 0.21 | 0.36 | 0.50 | 0.63 | 0.76 | 0.85 |
| just-sort-it (reference) | 0.19 | 0.31 | 0.46 | 0.60 | 0.71 | 0.93 |
| ford-johnson (reference) | 0.23 | 0.41 | 0.53 | 0.56 | 0.62 | 0.90 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 73% | 57% | 0/10 |
| **rankify-mixed** | 80% | 37% | 10/10 |
| elo | 78% | 31% | 0/10 |
| glicko2 | 78% | 31% | 0/10 |
| just-sort-it (reference) | 74% | 36% | 0/10 |
| ford-johnson (reference) | 0% | 0% | 10/10 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 50 | human | 0.028 | 93% |
| **rankify** | 50 | normal | 0.030 | 98% |
| **rankify-mixed** | 50 | human | 0.036 | 89% |
| **rankify-mixed** | 50 | normal | 0.047 | 98% |
| glicko2 | 50 | human | 0.014 | 93% |
| glicko2 | 50 | normal | 0.049 | 99% |
| just-sort-it (reference) | 50 | human | 0.014 | 95% |
| just-sort-it (reference) | 50 | normal | 0.044 | 97% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/20 lists; median τ between the two rankings 1.00
- rankify-mixed: #1 changed in 0/20 lists; median τ between the two rankings 1.00
- elo: #1 changed in 5/20 lists; median τ between the two rankings 0.93
- glicko2: #1 changed in 3/20 lists; median τ between the two rankings 0.95

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 7.1 | 7.7 | 1.6 |
| **rankify-mixed** | 9.1 | 8.6 | 1.6 |
| elo | 1.4 | 3.3 | 1.5 |
| glicko2 | 1.5 | 7.7 | 1.6 |
| just-sort-it (reference) | 3.1 | 8.4 | 1.6 |
| ford-johnson (reference) | 1.9 | 6.4 | 1.6 |

A real `rankify` subprocess (20 items, includes Python start-up): next 911 ms, answer 77 ms, show 74 ms.

## What each method offers

| Feature | rankify | rankify-mixed | elo | glicko2 | just-sort-it | ford-johnson |
|---|---|---|---|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | yes: order information per second, weighted by the mode | no: random pairs | no: random pairs | yes: quicksort | yes: merge insertion |
| Knows when it is done | yes: confidence target, or nothing worth asking | yes: confidence target, or nothing worth asking | no | no | no | yes, but trusts every answer |
| Rounds left | yes: simulated, with a 10–90% range | yes: simulated, with a 10–90% range | no | no | no | no |
| Precision modes | yes: quick, stable, exact | yes: quick, stable, exact | no | no | no | no |
| Pick / rank rounds | no; `new --rounds mixed` adds them | yes: picks and rankings of 3 to 5, when they teach more per second | no | no | no | no |
| Confidence and Could be | yes | yes | no | yes (from RD) | yes (our fit) | while sorting (our fit) |
| Same answers, any order, same ranking | yes | yes | no: updates one match at a time | no: updates one match at a time | yes | yes |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
- How long a person takes to pick from or rank 3 to 5 items is a guess in both the judge and the planner. The planner switches to the judge's own times after 8 answers of a kind and size.
