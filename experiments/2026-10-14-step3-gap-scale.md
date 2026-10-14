# Benchmark: rankify against rating systems for human judges

- Date: 2026-10-14 03:11 UTC
- Code: commit 9769c30 + uncommitted changes, engine 0.3.0
- Setup: 10, 20 items; judges: human, noisy, normal, perfect; 50 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 395 s for 1200 runs; the other 800 came from the cache.
- Every method ran through the service calls behind the CLI: a new list with the method, then next round, answer (or can't decide) and ranking each round, in one session held open as the TUI holds it.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify as shipped (pairs); rankify-mixed (the same with `new --rounds mixed`, which also asks picks and rankings of 3 to 5 items); when run, two planner variants that check rankify's design (rankify-closest asks the relevant pair closest to 50/50, rankify-per-round counts information per round, not per second; both stop by rankify's rules); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and three sorts as reference lines only (Just Sort It, binary insertion, and Ford–Johnson merge insertion, which needs the fewest comparisons). The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes, as accurate as the human judge. **sharp**, **normal**, **fuzzy**: the model rankify assumes, telling neighbours on a 20-item list apart 90%, 75% and 60% of the time. The rest are normal with one twist: **careless** answers 5% at random; **biased** favours the item shown first (60% between equals); **thurstone** has normal-curve noise; **similar** gives a quarter of the items a near-identical twin, and twins shown together in a pick or ordering split one option's chance (Debreu 1960); **tired** gets 1% noisier every round.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 74% | 4% | 2.9 |
| noisy | 78% | 0% | 2.9 |
| normal | 89% | 0% | 3.0 |
| perfect | 100% | 0% | 2.9 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 41 · 1.9 min (39/50) | 77 · 3.8 min (35/50) | — (23/50) |
| elo | 71 · 3.1 min (42/50) | 122 · 5.2 min (34/50) | — (7/50) |
| just-sort-it (reference) | 65 · 2.9 min (40/50) | 90 · 3.8 min (38/50) | — (18/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 36/50 | #1 right in 44/50 | 83 | 4.1 |
| stable | 50/50 | 30/50 | 91% of pairs right | 118 | 6.1 |
| exact | 26/50 | 9/26 | 89% of pairs right | 178 | 9.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 63%, stable 73%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 67%, stable 100%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 212 | 90% | 20% | 0 | 0 |
| rankify | stable | 238 | 81% | 29% | 0 | 0 |
| rankify | exact | 130 | 100% | 20% | 0 | 120 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.51 | 0.76 | 0.82 | 0.87 | 0.91 |
| elo | 0.44 | 0.60 | 0.73 | 0.82 | 0.82 |
| just-sort-it (reference) | 0.42 | 0.64 | 0.78 | 0.87 | 0.87 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 87% | 79% | 26/50 |
| elo | 91% | 77% | 0/50 |
| just-sort-it (reference) | 86% | 74% | 0/50 |

## 20 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 64 · 3.0 min (35/50) | — (17/50) | — (0/50) |
| elo | 267 · 11.4 min (34/50) | — (13/50) | — (0/50) |
| just-sort-it (reference) | 154 · 6.7 min (36/50) | — (18/50) | — (0/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 29/50 | #1 right in 49/50 | 106 | 4.9 |
| stable | 50/50 | 12/50 | 86% of pairs right | 198 | 9.9 |
| exact | 0/50 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 26%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 44%, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 235 | 92% | 17% | 0 | 0 |
| rankify | stable | 250 | 93% | 16% | 0 | 0 |
| rankify | exact | 0 | — | — | 0 | 250 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.29 | 0.53 | 0.65 | 0.75 | 0.82 | 0.87 |
| elo | 0.33 | 0.47 | 0.59 | 0.70 | 0.75 | 0.82 |
| just-sort-it (reference) | 0.29 | 0.45 | 0.59 | 0.71 | 0.79 | 0.83 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 87% | 72% | 0/50 |
| elo | 90% | 58% | 0/50 |
| just-sort-it (reference) | 84% | 57% | 0/50 |

## 10 items, noisy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 32 · 1.4 min (44/50) | 66 · 3.2 min (39/50) | — (23/50) |
| elo | 58 · 2.3 min (46/50) | 88 · 3.5 min (42/50) | — (10/50) |
| just-sort-it (reference) | 46 · 1.9 min (47/50) | 64 · 2.8 min (45/50) | — (13/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 42/50 | #1 right in 48/50 | 78 | 3.8 |
| stable | 50/50 | 34/50 | 94% of pairs right | 107 | 5.7 |
| exact | 45/50 | 19/45 | 90% of pairs right | 178 | 9.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 60%, stable 92%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 71%, stable 116%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 206 | 93% | 23% | 0 | 0 |
| rankify | stable | 237 | 87% | 25% | 0 | 0 |
| rankify | exact | 225 | 96% | 18% | 0 | 25 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.56 | 0.73 | 0.82 | 0.91 | 0.91 |
| elo | 0.47 | 0.62 | 0.73 | 0.82 | 0.87 |
| just-sort-it (reference) | 0.51 | 0.73 | 0.82 | 0.87 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 84% | 77% | 45/50 |
| elo | 91% | 77% | 0/50 |
| just-sort-it (reference) | 87% | 75% | 0/50 |

## 20 items, noisy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 54 · 2.2 min (41/50) | — (25/50) | — (8/50) |
| elo | 182 · 7.7 min (37/50) | — (17/50) | — (0/50) |
| just-sort-it (reference) | 106 · 4.7 min (45/50) | 338 · 15.8 min (27/50) | — (0/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 38/50 | #1 right in 48/50 | 100 | 4.7 |
| stable | 50/50 | 19/50 | 87% of pairs right | 180 | 9.4 |
| exact | 2/50 | 1/2 | 91% of pairs right | 398 | 21.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 29%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 48%, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.3 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 226 | 86% | 21% | 0 | 0 |
| rankify | stable | 250 | 94% | 12% | 0 | 0 |
| rankify | exact | 10 | 100% | 29% | 0 | 240 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.28 | 0.55 | 0.68 | 0.78 | 0.88 | 0.93 |
| elo | 0.31 | 0.46 | 0.61 | 0.68 | 0.79 | 0.84 |
| just-sort-it (reference) | 0.26 | 0.43 | 0.61 | 0.76 | 0.84 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 86% | 73% | 2/50 |
| elo | 89% | 58% | 0/50 |
| just-sort-it (reference) | 84% | 58% | 0/50 |

## 10 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 19 · 0.8 min (50/50) | 26 · 1.1 min (50/50) | 42 · 2.0 min (50/50) |
| elo | 54 · 2.3 min (49/50) | 72 · 3.4 min (49/50) | 166 · 7.1 min (30/50) |
| just-sort-it (reference) | 25 · 1.0 min (50/50) | 27 · 1.3 min (50/50) | 64 · 2.8 min (46/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 50/50 | #1 right in 50/50 | 58 | 2.8 |
| stable | 50/50 | 49/50 | 100% of pairs right | 80 | 4.1 |
| exact | 50/50 | 50/50 | 100% of pairs right | 130 | 7.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 36%, stable 33%, exact 29%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 80%, stable 88%, exact 73%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.7 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 183 | 68% | 59% | 0 | 0 |
| rankify | stable | 207 | 88% | 28% | 0 | 0 |
| rankify | exact | 249 | 63% | 55% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.64 | 0.89 | 0.96 | 1.00 | 1.00 |
| elo | 0.51 | 0.71 | 0.82 | 0.87 | 0.93 |
| just-sort-it (reference) | 0.53 | 0.82 | 0.96 | 0.96 | 0.96 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 56% | 46% | 50/50 |
| elo | 86% | 72% | 0/50 |
| just-sort-it (reference) | 68% | 54% | 0/50 |

## 20 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 42 · 1.9 min (49/50) | 71 · 3.6 min (48/50) | 160 · 9.0 min (49/50) |
| elo | 186 · 8.3 min (42/50) | 342 · 15.4 min (28/50) | — (3/50) |
| just-sort-it (reference) | 88 · 4.5 min (50/50) | 118 · 5.8 min (49/50) | 260 · 13.1 min (38/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 49/50 | #1 right in 50/50 | 66 | 3.0 |
| stable | 50/50 | 47/50 | 99% of pairs right | 144 | 8.0 |
| exact | 42/50 | 40/42 | 100% of pairs right | 361 | 22.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 22%, stable 24%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 41%, stable 63%, exact 69%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 3.1 s | 0% | 0% |
| rankify | exact | 100% · 3.7 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 204 | 60% | 82% | 0 | 0 |
| rankify | stable | 250 | 89% | 28% | 0 | 0 |
| rankify | exact | 210 | 70% | 44% | 0 | 40 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.37 | 0.65 | 0.83 | 0.94 | 0.97 | 0.98 |
| elo | 0.36 | 0.54 | 0.66 | 0.75 | 0.85 | 0.91 |
| just-sort-it (reference) | 0.30 | 0.48 | 0.71 | 0.90 | 0.95 | 0.97 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 62% | 47% | 42/50 |
| elo | 84% | 58% | 0/50 |
| just-sort-it (reference) | 75% | 50% | 0/50 |

## 10 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 16 · 0.8 min (50/50) | 17 · 0.8 min (50/50) | 27 · 1.2 min (50/50) |
| elo | 52 · 2.2 min (49/50) | 68 · 3.1 min (49/50) | 150 · 6.5 min (35/50) |
| just-sort-it (reference) | 25 · 1.0 min (50/50) | 26 · 1.2 min (50/50) | 36 · 1.6 min (50/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 50/50 | #1 right in 50/50 | 39 | 1.8 |
| stable | 50/50 | 50/50 | 100% of pairs right | 61 | 2.9 |
| exact | 50/50 | 50/50 | 100% of pairs right | 85 | 4.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 34%, stable 25%, exact 19%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 72%, stable 64%, exact 79%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 2.9 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 150 | 23% | 167% | 0 | 0 |
| rankify | stable | 200 | 78% | 56% | 0 | 0 |
| rankify | exact | 200 | 25% | 154% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.64 | 0.96 | 1.00 | 1.00 | 1.00 |
| elo | 0.51 | 0.76 | 0.82 | 0.91 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.87 | 1.00 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 17% | 5% | 50/50 |
| elo | 84% | 72% | 0/50 |
| just-sort-it (reference) | 31% | 17% | 0/50 |

## 20 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 38 · 1.7 min (50/50) | 62 · 2.8 min (50/50) | 81 · 4.1 min (50/50) |
| elo | 194 · 8.4 min (40/50) | 384 · 16.6 min (26/50) | — (0/50) |
| just-sort-it (reference) | 94 · 4.7 min (50/50) | 102 · 5.1 min (50/50) | 128 · 6.2 min (50/50) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 50/50 | 50/50 | #1 right in 50/50 | 58 | 2.5 |
| stable | 50/50 | 50/50 | 100% of pairs right | 104 | 5.3 |
| exact | 50/50 | 50/50 | 100% of pairs right | 180 | 10.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 20%, stable 17%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 35%, stable 55%, exact 66%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 200 | 32% | 140% | 0 | 0 |
| rankify | stable | 241 | 52% | 79% | 0 | 0 |
| rankify | exact | 250 | 0% | 201% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.37 | 0.67 | 0.87 | 1.00 | 1.00 | 1.00 |
| elo | 0.38 | 0.56 | 0.68 | 0.77 | 0.86 | 0.92 |
| just-sort-it (reference) | 0.30 | 0.48 | 0.71 | 0.94 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 17% | 5% | 50/50 |
| elo | 81% | 58% | 0/50 |
| just-sort-it (reference) | 42% | 21% | 0/50 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 10 | human | 0.037 | 94% |
| **rankify** | 10 | noisy | 0.028 | 97% |
| **rankify** | 10 | normal | 0.025 | 99% |
| **rankify** | 10 | perfect | 0.035 | 100% |
| **rankify** | 20 | human | 0.028 | 90% |
| **rankify** | 20 | noisy | 0.017 | 93% |
| **rankify** | 20 | normal | 0.029 | 98% |
| **rankify** | 20 | perfect | 0.034 | 100% |
| just-sort-it (reference) | 10 | human | 0.039 | 97% |
| just-sort-it (reference) | 10 | noisy | 0.022 | 96% |
| just-sort-it (reference) | 10 | normal | 0.037 | 99% |
| just-sort-it (reference) | 10 | perfect | 0.030 | 100% |
| just-sort-it (reference) | 20 | human | 0.020 | 94% |
| just-sort-it (reference) | 20 | noisy | 0.023 | 96% |
| just-sort-it (reference) | 20 | normal | 0.037 | 99% |
| just-sort-it (reference) | 20 | perfect | 0.053 | 100% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/400 lists; median τ between the two rankings 1.00
- elo: #1 changed in 41/400 lists; median τ between the two rankings 0.95

## Compute cost per round

Median milliseconds per call, through the service layer in one open session (the CLI's `next`, `answer` and `show` add command parsing, JSON and opening the database):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 0.6 | 3.0 | 0.1 |
| elo | 1.4 | 2.3 | 1.4 |
| just-sort-it (reference) | 2.0 | 4.7 | 1.5 |

A real `rankify` subprocess (20 items, includes Python start-up): next 149 ms, answer 80 ms, show 73 ms.

## What each method offers

| Feature | rankify | elo | just-sort-it |
|---|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | no: random pairs | yes: quicksort |
| Knows when it is done | yes: confidence target, or nothing worth asking | no | no |
| Rounds left | yes: simulated, with a 10–90% range | no | no |
| Precision modes | yes: quick, stable, exact | no | no |
| Pick / rank rounds | no; `new --rounds mixed` adds them | no | no |
| Confidence and Could be | yes | no | yes (our fit) |
| Same answers, any order, same ranking | yes | no: updates one match at a time | yes |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
- How long a person takes to pick from or rank 3 to 5 items is a guess in both the judge and the planner. The planner switches to the judge's own times after 8 answers of a kind and size.
