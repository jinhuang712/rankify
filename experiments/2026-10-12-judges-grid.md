# Benchmark: rankify against rating systems for human judges

- Date: 2026-10-12 11:24 UTC
- Code: commit fef1db1 + uncommitted changes, engine 0.3.0
- Setup: 10, 20 items; judges: human, perfect, noisy, sharp, normal, fuzzy, careless, biased, thurstone, similar, tired; 20 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 6056 s for 3680 runs; the other 720 came from the cache.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify as shipped (pairs); rankify-mixed (the same with `new --rounds mixed`, which also asks picks and rankings of 3 to 5 items); when run, two planner variants that check rankify's design (rankify-closest asks the relevant pair closest to 50/50, rankify-per-round counts information per round, not per second; both stop by rankify's rules); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and three sorts as reference lines only (Just Sort It, binary insertion, and Ford–Johnson merge insertion, which needs the fewest comparisons). The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes, as accurate as the human judge. **sharp**, **normal**, **fuzzy**: the model rankify assumes, telling neighbours on a 20-item list apart 90%, 75% and 60% of the time. The rest are normal with one twist: **careless** answers 5% at random; **biased** favours the item shown first (60% between equals); **thurstone** has normal-curve noise; **similar** gives a quarter of the items a near-identical twin, and twins shown together in a pick or ordering split one option's chance (Debreu 1960); **tired** gets 1% noisier every round.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 73% | 4% | 3.5 |
| perfect | 100% | 0% | 3.2 |
| noisy | 77% | 0% | 3.4 |
| sharp | 94% | 0% | 3.3 |
| normal | 90% | 0% | 3.4 |
| fuzzy | 80% | 0% | 3.5 |
| careless | 88% | 0% | 3.4 |
| biased | 89% | 0% | 3.4 |
| thurstone | 90% | 0% | 3.4 |
| similar | 87% | 0% | 3.6 |
| tired | 83% | 0% | 3.4 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 39 · 1.8 min (16/20) | 73 · 3.3 min (14/20) | — (10/20) |
| **rankify-mixed** | 12 · 1.3 min (18/20) | 36 · 4.0 min (14/20) | — (10/20) |
| elo | 64 · 2.8 min (17/20) | 118 · 5.0 min (13/20) | — (2/20) |
| glicko2 | 70 · 3.1 min (17/20) | 131 · 5.4 min (14/20) | — (5/20) |
| just-sort-it (reference) | 54 · 2.4 min (18/20) | 80 · 3.5 min (16/20) | — (7/20) |
| ford-johnson (reference) | — (5/20) | — (4/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 15/20 | #1 right in 17/20 | 84 | 4.0 |
| stable | 20/20 | 14/20 | 92% of pairs right | 116 | 5.9 |
| exact | 9/20 | 5/9 | 94% of pairs right | 172 | 8.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 20/20 | 32 | 3.6 |
| stable | 20/20 | 14/20 | 92% of pairs right | 46 | 5.1 |
| exact | 20/20 | 8/20 | 88% of pairs right | 69 | 8.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 66%, stable 67%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 76%, stable 95%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 74%, stable 121%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.0 s | 0% | 0% |
| rankify-mixed | quick | 21% · 3.3 s | 7% · 3.5 s | 72% · 8.0 s |
| rankify-mixed | stable | 30% · 3.1 s | 5% · 3.4 s | 64% · 8.2 s |
| rankify-mixed | exact | 19% · 3.4 s | 3% · 3.5 s | 78% · 8.8 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 84 | 68% | 20% | 0 | 0 |
| rankify | stable | 94 | 73% | 16% | 0 | 0 |
| rankify | exact | 45 | 51% | 24% | 0 | 55 |
| rankify-mixed | quick | 57 | 72% | 33% | 0 | 0 |
| rankify-mixed | stable | 66 | 82% | 19% | 0 | 0 |
| rankify-mixed | exact | 79 | 68% | 30% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.49 | 0.80 | 0.82 | 0.89 | 0.91 |
| **rankify-mixed** | 0.80 | 0.87 | 0.91 | 0.96 | 0.96 |
| elo | 0.49 | 0.60 | 0.78 | 0.82 | 0.84 |
| glicko2 | 0.49 | 0.62 | 0.73 | 0.84 | 0.87 |
| just-sort-it (reference) | 0.44 | 0.69 | 0.80 | 0.87 | 0.91 |
| ford-johnson (reference) | 0.49 | 0.71 | 0.71 | 0.71 | 0.71 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 86% | 78% | 9/20 |
| **rankify-mixed** | 87% | 57% | 20/20 |
| elo | 91% | 77% | 0/20 |
| glicko2 | 90% | 76% | 0/20 |
| just-sort-it (reference) | 86% | 74% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 74 · 3.4 min (12/20) | — (5/20) | — (0/20) |
| **rankify-mixed** | 28 · 3.6 min (13/20) | — (3/20) | — (0/20) |
| elo | 315 · 13.3 min (12/20) | — (4/20) | — (0/20) |
| glicko2 | 126 · 5.6 min (15/20) | — (2/20) | — (0/20) |
| just-sort-it (reference) | 141 · 6.0 min (15/20) | — (5/20) | — (0/20) |
| ford-johnson (reference) | — (6/20) | — (0/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 10/20 | #1 right in 19/20 | 90 | 3.9 |
| stable | 20/20 | 4/20 | 85% of pairs right | 199 | 10.1 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 12/20 | #1 right in 19/20 | 36 | 4.5 |
| stable | 20/20 | 3/20 | 90% of pairs right | 72 | 10.5 |
| exact | 20/20 | 0/20 | 77% of pairs right | 154 | 21.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 25%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 56%, stable n/a, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 108%, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 13% · 2.9 s | 6% · 3.8 s | 82% · 7.8 s |
| rankify-mixed | stable | 12% · 3.1 s | 3% · 3.9 s | 85% · 8.8 s |
| rankify-mixed | exact | 22% · 3.4 s | 2% · 3.9 s | 76% · 9.2 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 85 | 81% | 16% | 0 | 0 |
| rankify | stable | 100 | 72% | 18% | 0 | 0 |
| rankify | exact | 0 | — | — | 0 | 100 |
| rankify-mixed | quick | 61 | 77% | 29% | 0 | 0 |
| rankify-mixed | stable | 81 | 79% | 22% | 0 | 0 |
| rankify-mixed | exact | 100 | 55% | 23% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.26 | 0.54 | 0.68 | 0.79 | 0.83 | 0.86 |
| **rankify-mixed** | 0.57 | 0.74 | 0.83 | 0.87 | 0.89 | 0.89 |
| elo | 0.33 | 0.49 | 0.63 | 0.69 | 0.73 | 0.79 |
| glicko2 | 0.33 | 0.52 | 0.63 | 0.71 | 0.76 | 0.81 |
| just-sort-it (reference) | 0.29 | 0.44 | 0.61 | 0.71 | 0.77 | 0.83 |
| ford-johnson (reference) | 0.34 | 0.48 | 0.64 | 0.67 | 0.67 | 0.67 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 87% | 73% | 0/20 |
| **rankify-mixed** | 90% | 35% | 20/20 |
| elo | 90% | 58% | 0/20 |
| glicko2 | 90% | 58% | 0/20 |
| just-sort-it (reference) | 84% | 57% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 15 · 0.7 min (20/20) | 16 · 0.7 min (20/20) | 29 · 1.3 min (20/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 6 · 0.9 min (20/20) | 8 · 1.0 min (20/20) |
| elo | 46 · 2.0 min (19/20) | 74 · 3.2 min (19/20) | 156 · 6.8 min (12/20) |
| glicko2 | 44 · 1.8 min (20/20) | 52 · 2.1 min (19/20) | 92 · 3.6 min (19/20) |
| just-sort-it (reference) | 26 · 1.1 min (20/20) | 30 · 1.3 min (20/20) | 36 · 1.6 min (20/20) |
| ford-johnson (reference) | 16 · 0.7 min (20/20) | 21 · 0.9 min (20/20) | 22 · 1.0 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 39 | 1.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 64 | 3.1 |
| exact | 20/20 | 20/20 | 100% of pairs right | 85 | 4.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 14 | 1.6 |
| stable | 20/20 | 20/20 | 100% of pairs right | 24 | 2.7 |
| exact | 20/20 | 20/20 | 100% of pairs right | 37 | 3.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 35%, stable 21%, exact 19%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 64%, stable 52%, exact 82%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 91%, stable 125%, exact 77%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.6 s | 0% | 0% |
| rankify | exact | 100% · 2.8 s | 0% | 0% |
| rankify-mixed | quick | 11% · 2.8 s | 15% · 3.5 s | 74% · 7.7 s |
| rankify-mixed | stable | 27% · 2.9 s | 9% · 3.5 s | 64% · 8.1 s |
| rankify-mixed | exact | 45% · 3.4 s | 6% · 3.6 s | 49% · 8.2 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 60 | 13% | 188% | 0 | 0 |
| rankify | stable | 80 | 26% | 96% | 0 | 0 |
| rankify | exact | 80 | 21% | 163% | 0 | 0 |
| rankify-mixed | quick | 40 | 28% | 200% | 0 | 0 |
| rankify-mixed | stable | 50 | 24% | 112% | 0 | 0 |
| rankify-mixed | exact | 60 | 28% | 171% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.96 | 1.00 | 1.00 | 1.00 |
| **rankify-mixed** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| elo | 0.47 | 0.71 | 0.84 | 0.91 | 0.96 |
| glicko2 | 0.49 | 0.78 | 0.89 | 1.00 | 1.00 |
| just-sort-it (reference) | 0.56 | 0.87 | 1.00 | 1.00 | 1.00 |
| ford-johnson (reference) | 0.69 | 1.00 | 1.00 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 17% | 5% | 20/20 |
| **rankify-mixed** | 9% | 0% | 20/20 |
| elo | 83% | 72% | 0/20 |
| glicko2 | 74% | 60% | 0/20 |
| just-sort-it (reference) | 28% | 15% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 34 · 1.6 min (20/20) | 72 · 3.2 min (20/20) | 81 · 4.1 min (20/20) |
| **rankify-mixed** | 13 · 1.6 min (20/20) | 14 · 2.0 min (20/20) | 22 · 3.0 min (20/20) |
| elo | 191 · 8.4 min (18/20) | 374 · 16.2 min (11/20) | — (0/20) |
| glicko2 | 89 · 4.0 min (19/20) | 270 · 11.6 min (15/20) | — (3/20) |
| just-sort-it (reference) | 98 · 4.7 min (20/20) | 110 · 5.2 min (20/20) | 128 · 6.2 min (20/20) |
| ford-johnson (reference) | 24 · 1.1 min (20/20) | 62 · 3.2 min (20/20) | 62 · 3.2 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 62 | 2.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 131 | 6.7 |
| exact | 20/20 | 20/20 | 100% of pairs right | 250 | 13.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 20 | 2.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 38 | 4.9 |
| exact | 20/20 | 20/20 | 100% of pairs right | 118 | 12.3 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 19%, stable 19%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 34%, stable 61%, exact 66%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 100%, stable 63%, exact 74%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 7% · 2.4 s | 10% · 3.6 s | 83% · 8.1 s |
| rankify-mixed | stable | 18% · 3.4 s | 8% · 4.1 s | 75% · 8.7 s |
| rankify-mixed | exact | 58% · 4.0 s | 2% · 4.0 s | 40% · 8.9 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 80 | 19% | 87% | 0 | 0 |
| rankify | stable | 100 | 13% | 73% | 0 | 0 |
| rankify | exact | 100 | 0% | 121% | 0 | 0 |
| rankify-mixed | quick | 41 | 2% | 145% | 0 | 0 |
| rankify-mixed | stable | 62 | 21% | 124% | 0 | 0 |
| rankify-mixed | exact | 100 | 58% | 51% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.37 | 0.67 | 0.87 | 1.00 | 1.00 | 1.00 |
| **rankify-mixed** | 0.76 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| elo | 0.42 | 0.53 | 0.68 | 0.76 | 0.85 | 0.91 |
| glicko2 | 0.42 | 0.57 | 0.73 | 0.84 | 0.92 | 0.96 |
| just-sort-it (reference) | 0.27 | 0.36 | 0.72 | 0.94 | 1.00 | 1.00 |
| ford-johnson (reference) | 0.43 | 0.61 | 0.73 | 1.00 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 16% | 5% | 20/20 |
| **rankify-mixed** | 7% | 0% | 20/20 |
| elo | 81% | 58% | 0/20 |
| glicko2 | 81% | 57% | 0/20 |
| just-sort-it (reference) | 39% | 21% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, noisy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 28 · 1.2 min (18/20) | 52 · 2.6 min (18/20) | 112 · 5.9 min (12/20) |
| **rankify-mixed** | 12 · 1.2 min (16/20) | 20 · 2.2 min (18/20) | 46 · 6.8 min (13/20) |
| elo | 48 · 2.0 min (18/20) | 74 · 3.3 min (17/20) | — (2/20) |
| glicko2 | 49 · 2.2 min (18/20) | 68 · 3.2 min (16/20) | — (6/20) |
| just-sort-it (reference) | 48 · 2.0 min (19/20) | 60 · 2.6 min (19/20) | — (5/20) |
| ford-johnson (reference) | — (5/20) | — (5/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 19/20 | 73 | 3.6 |
| stable | 20/20 | 17/20 | 97% of pairs right | 102 | 5.3 |
| exact | 19/20 | 11/19 | 94% of pairs right | 170 | 9.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 16/20 | #1 right in 19/20 | 30 | 3.4 |
| stable | 20/20 | 18/20 | 94% of pairs right | 40 | 5.0 |
| exact | 20/20 | 12/20 | 95% of pairs right | 72 | 8.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 61%, stable 79%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 59%, stable 98%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 101%, stable 83%, exact 116%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 20% · 3.0 s | 7% · 3.5 s | 73% · 8.2 s |
| rankify-mixed | stable | 27% · 3.1 s | 5% · 3.5 s | 68% · 8.3 s |
| rankify-mixed | exact | 36% · 3.4 s | 3% · 3.7 s | 61% · 8.6 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 80 | 78% | 28% | 0 | 0 |
| rankify | stable | 92 | 65% | 24% | 0 | 0 |
| rankify | exact | 95 | 39% | 26% | 0 | 5 |
| rankify-mixed | quick | 56 | 64% | 33% | 0 | 0 |
| rankify-mixed | stable | 62 | 71% | 32% | 0 | 0 |
| rankify-mixed | exact | 81 | 72% | 22% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.56 | 0.80 | 0.84 | 0.91 | 0.96 |
| **rankify-mixed** | 0.80 | 0.91 | 0.91 | 0.93 | 0.93 |
| elo | 0.51 | 0.67 | 0.73 | 0.80 | 0.87 |
| glicko2 | 0.49 | 0.64 | 0.78 | 0.82 | 0.89 |
| just-sort-it (reference) | 0.51 | 0.73 | 0.82 | 0.87 | 0.89 |
| ford-johnson (reference) | 0.47 | 0.78 | 0.78 | 0.78 | 0.78 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 83% | 74% | 19/20 |
| **rankify-mixed** | 85% | 51% | 20/20 |
| elo | 90% | 77% | 0/20 |
| glicko2 | 89% | 75% | 0/20 |
| just-sort-it (reference) | 87% | 75% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, noisy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | — (10/20) | — (8/20) | — (0/20) |
| **rankify-mixed** | 22 · 3.1 min (12/20) | 51 · 7.1 min (13/20) | — (1/20) |
| elo | 194 · 8.7 min (15/20) | — (9/20) | — (0/20) |
| glicko2 | 104 · 4.3 min (15/20) | — (9/20) | — (0/20) |
| just-sort-it (reference) | 150 · 6.8 min (17/20) | 277 · 13.1 min (12/20) | — (0/20) |
| ford-johnson (reference) | 56 · 2.6 min (12/20) | — (0/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 10/20 | #1 right in 19/20 | 86 | 3.8 |
| stable | 20/20 | 5/20 | 83% of pairs right | 196 | 9.5 |
| exact | 1/20 | 0/1 | 94% of pairs right | 393 | 22.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 12/20 | #1 right in 19/20 | 34 | 4.6 |
| stable | 20/20 | 13/20 | 93% of pairs right | 71 | 9.0 |
| exact | 20/20 | 0/20 | 83% of pairs right | 164 | 21.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick n/a, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick n/a, stable n/a, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick n/a, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |
| rankify-mixed | quick | 12% · 3.4 s | 6% · 3.4 s | 82% · 8.2 s |
| rankify-mixed | stable | 16% · 3.1 s | 4% · 3.6 s | 80% · 9.0 s |
| rankify-mixed | exact | 34% · 3.6 s | 2% · 3.7 s | 65% · 9.5 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 77% | 19% | 0 | 0 |
| rankify | stable | 100 | 76% | 15% | 0 | 0 |
| rankify | exact | 5 | 20% | 38% | 0 | 95 |
| rankify-mixed | quick | 58 | 71% | 35% | 0 | 0 |
| rankify-mixed | stable | 78 | 69% | 25% | 0 | 0 |
| rankify-mixed | exact | 100 | 57% | 25% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.28 | 0.57 | 0.68 | 0.81 | 0.88 | 0.93 |
| **rankify-mixed** | 0.60 | 0.79 | 0.85 | 0.91 | 0.93 | 0.93 |
| elo | 0.30 | 0.45 | 0.59 | 0.67 | 0.77 | 0.85 |
| glicko2 | 0.29 | 0.47 | 0.64 | 0.73 | 0.78 | 0.87 |
| just-sort-it (reference) | 0.26 | 0.46 | 0.61 | 0.75 | 0.83 | 0.91 |
| ford-johnson (reference) | 0.32 | 0.51 | 0.64 | 0.74 | 0.74 | 0.74 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 86% | 73% | 1/20 |
| **rankify-mixed** | 90% | 39% | 20/20 |
| elo | 89% | 58% | 0/20 |
| glicko2 | 89% | 58% | 0/20 |
| just-sort-it (reference) | 83% | 58% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, sharp judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 19 · 0.8 min (20/20) | 17 · 0.8 min (20/20) | 27 · 1.3 min (20/20) |
| **rankify-mixed** | 5 · 0.5 min (20/20) | 6 · 0.7 min (20/20) | 9 · 1.0 min (20/20) |
| elo | 46 · 1.9 min (19/20) | 80 · 3.5 min (19/20) | 146 · 6.3 min (12/20) |
| glicko2 | 44 · 1.8 min (20/20) | 52 · 2.1 min (19/20) | 92 · 3.8 min (18/20) |
| just-sort-it (reference) | 28 · 1.2 min (20/20) | 31 · 1.4 min (20/20) | 36 · 1.7 min (20/20) |
| ford-johnson (reference) | 19 · 0.9 min (19/20) | 22 · 1.0 min (19/20) | 22 · 1.0 min (14/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 46 | 2.1 |
| stable | 20/20 | 20/20 | 100% of pairs right | 68 | 3.6 |
| exact | 20/20 | 20/20 | 100% of pairs right | 144 | 7.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 16 | 1.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 27 | 3.1 |
| exact | 20/20 | 20/20 | 100% of pairs right | 54 | 6.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 42%, stable 22%, exact 20%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 70%, stable 57%, exact 75%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 64%, stable 88%, exact 82%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 2.9 s | 0% | 0% |
| rankify-mixed | quick | 27% · 4.2 s | 10% · 3.5 s | 63% · 7.8 s |
| rankify-mixed | stable | 31% · 4.0 s | 8% · 3.5 s | 61% · 8.5 s |
| rankify-mixed | exact | 39% · 3.7 s | 5% · 3.9 s | 56% · 8.4 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 69 | 36% | 92% | 0 | 0 |
| rankify | stable | 82 | 44% | 66% | 0 | 0 |
| rankify | exact | 97 | 35% | 52% | 0 | 0 |
| rankify-mixed | quick | 44 | 39% | 155% | 0 | 0 |
| rankify-mixed | stable | 55 | 40% | 88% | 0 | 0 |
| rankify-mixed | exact | 73 | 55% | 60% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.96 | 1.00 | 1.00 | 1.00 |
| **rankify-mixed** | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 |
| elo | 0.53 | 0.73 | 0.82 | 0.91 | 0.96 |
| glicko2 | 0.51 | 0.76 | 0.87 | 0.96 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.87 | 0.96 | 1.00 | 1.00 |
| ford-johnson (reference) | 0.67 | 0.96 | 0.96 | 0.96 | 0.96 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 17% | 6% | 20/20 |
| **rankify-mixed** | 24% | 4% | 20/20 |
| elo | 82% | 71% | 0/20 |
| glicko2 | 76% | 62% | 0/20 |
| just-sort-it (reference) | 42% | 27% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, sharp judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 31 · 1.4 min (20/20) | 66 · 3.1 min (20/20) | 96 · 5.1 min (20/20) |
| **rankify-mixed** | 13 · 1.6 min (20/20) | 16 · 2.1 min (20/20) | 29 · 3.9 min (20/20) |
| elo | 192 · 8.6 min (18/20) | 313 · 13.9 min (13/20) | — (1/20) |
| glicko2 | 85 · 3.8 min (19/20) | 242 · 10.7 min (17/20) | — (4/20) |
| just-sort-it (reference) | 98 · 4.6 min (20/20) | 108 · 5.2 min (20/20) | 145 · 7.1 min (20/20) |
| ford-johnson (reference) | 31 · 1.4 min (18/20) | 62 · 3.3 min (13/20) | — (7/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 62 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 164 | 8.7 |
| exact | 20/20 | 20/20 | 100% of pairs right | 354 | 21.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 24 | 3.1 |
| stable | 20/20 | 20/20 | 100% of pairs right | 50 | 6.6 |
| exact | 20/20 | 20/20 | 100% of pairs right | 167 | 16.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 16%, stable 22%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 30%, stable 59%, exact 72%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 118%, stable 70%, exact 77%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.4 s | 0% | 0% |
| rankify-mixed | quick | 12% · 4.5 s | 8% · 3.4 s | 80% · 8.2 s |
| rankify-mixed | stable | 23% · 4.1 s | 6% · 3.6 s | 72% · 9.3 s |
| rankify-mixed | exact | 65% · 4.2 s | 3% · 5.3 s | 32% · 9.0 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 80 | 39% | 70% | 0 | 0 |
| rankify | stable | 100 | 49% | 33% | 0 | 0 |
| rankify | exact | 100 | 11% | 53% | 0 | 0 |
| rankify-mixed | quick | 49 | 27% | 100% | 0 | 0 |
| rankify-mixed | stable | 71 | 39% | 65% | 0 | 0 |
| rankify-mixed | exact | 100 | 70% | 20% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.36 | 0.65 | 0.86 | 0.97 | 0.99 | 0.99 |
| **rankify-mixed** | 0.73 | 0.97 | 0.98 | 0.99 | 0.99 | 0.99 |
| elo | 0.42 | 0.56 | 0.66 | 0.75 | 0.84 | 0.91 |
| glicko2 | 0.42 | 0.57 | 0.72 | 0.82 | 0.91 | 0.95 |
| just-sort-it (reference) | 0.27 | 0.42 | 0.66 | 0.91 | 0.97 | 0.98 |
| ford-johnson (reference) | 0.39 | 0.59 | 0.70 | 0.96 | 0.96 | 0.96 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 34% | 18% | 20/20 |
| **rankify-mixed** | 39% | 5% | 20/20 |
| elo | 82% | 58% | 0/20 |
| glicko2 | 82% | 57% | 0/20 |
| just-sort-it (reference) | 55% | 33% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 20 · 0.9 min (20/20) | 24 · 1.0 min (20/20) | 40 · 1.9 min (20/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 7 · 0.8 min (20/20) | 12 · 1.3 min (20/20) |
| elo | 48 · 2.0 min (20/20) | 72 · 3.1 min (20/20) | — (10/20) |
| glicko2 | 36 · 1.5 min (20/20) | 50 · 2.0 min (20/20) | 92 · 3.7 min (16/20) |
| just-sort-it (reference) | 25 · 1.0 min (20/20) | 30 · 1.4 min (20/20) | 66 · 2.9 min (19/20) |
| ford-johnson (reference) | 22 · 1.0 min (14/20) | 22 · 1.0 min (12/20) | — (6/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 54 | 2.6 |
| stable | 20/20 | 20/20 | 100% of pairs right | 77 | 4.1 |
| exact | 20/20 | 20/20 | 100% of pairs right | 146 | 8.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 16 | 1.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 32 | 3.3 |
| exact | 20/20 | 20/20 | 100% of pairs right | 56 | 6.3 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 43%, stable 33%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 84%, stable 71%, exact 67%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 65%, stable 78%, exact 68%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.0 s | 0% | 0% |
| rankify-mixed | quick | 16% · 3.8 s | 11% · 3.5 s | 72% · 7.9 s |
| rankify-mixed | stable | 28% · 3.8 s | 6% · 3.5 s | 66% · 8.5 s |
| rankify-mixed | exact | 40% · 4.0 s | 4% · 3.8 s | 55% · 8.6 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 73 | 42% | 79% | 0 | 0 |
| rankify | stable | 83 | 43% | 56% | 0 | 0 |
| rankify | exact | 100 | 32% | 48% | 0 | 0 |
| rankify-mixed | quick | 43 | 28% | 173% | 0 | 0 |
| rankify-mixed | stable | 55 | 47% | 74% | 0 | 0 |
| rankify-mixed | exact | 78 | 56% | 56% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.93 | 0.98 | 1.00 | 1.00 |
| **rankify-mixed** | 0.93 | 1.00 | 1.00 | 0.98 | 0.98 |
| elo | 0.56 | 0.73 | 0.80 | 0.87 | 0.91 |
| glicko2 | 0.53 | 0.78 | 0.87 | 0.93 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.82 | 0.96 | 1.00 | 1.00 |
| ford-johnson (reference) | 0.62 | 0.91 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 50% | 40% | 20/20 |
| **rankify-mixed** | 33% | 4% | 20/20 |
| elo | 85% | 73% | 0/20 |
| glicko2 | 79% | 65% | 0/20 |
| just-sort-it (reference) | 67% | 53% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 42 · 1.8 min (20/20) | 79 · 3.8 min (19/20) | 168 · 9.5 min (20/20) |
| **rankify-mixed** | 14 · 1.8 min (19/20) | 18 · 2.4 min (20/20) | 56 · 7.7 min (19/20) |
| elo | 204 · 9.0 min (16/20) | 354 · 15.6 min (11/20) | — (1/20) |
| glicko2 | 124 · 5.2 min (18/20) | 258 · 11.3 min (16/20) | — (2/20) |
| just-sort-it (reference) | 100 · 4.7 min (20/20) | 120 · 5.6 min (20/20) | 303 · 14.3 min (15/20) |
| ford-johnson (reference) | 40 · 2.0 min (15/20) | — (8/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 66 | 3.0 |
| stable | 20/20 | 19/20 | 100% of pairs right | 175 | 9.5 |
| exact | 17/20 | 17/17 | 100% of pairs right | 365 | 23.3 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 29 | 3.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 59 | 8.4 |
| exact | 20/20 | 19/20 | 100% of pairs right | 164 | 16.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 20%, stable 24%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 38%, stable 67%, exact 67%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 101%, stable 65%, exact 81%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-mixed | quick | 11% · 3.8 s | 7% · 3.3 s | 82% · 8.4 s |
| rankify-mixed | stable | 17% · 4.1 s | 5% · 3.3 s | 78% · 9.5 s |
| rankify-mixed | exact | 58% · 4.2 s | 2% · 4.1 s | 39% · 9.5 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 44% | 67% | 0 | 0 |
| rankify | stable | 100 | 65% | 21% | 0 | 0 |
| rankify | exact | 85 | 14% | 46% | 0 | 15 |
| rankify-mixed | quick | 52 | 42% | 63% | 0 | 0 |
| rankify-mixed | stable | 76 | 64% | 37% | 0 | 0 |
| rankify-mixed | exact | 100 | 68% | 22% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.64 | 0.84 | 0.94 | 0.97 | 0.98 |
| **rankify-mixed** | 0.71 | 0.93 | 0.97 | 0.98 | 0.99 | 0.99 |
| elo | 0.40 | 0.52 | 0.63 | 0.74 | 0.84 | 0.89 |
| glicko2 | 0.39 | 0.55 | 0.71 | 0.80 | 0.89 | 0.94 |
| just-sort-it (reference) | 0.27 | 0.42 | 0.68 | 0.89 | 0.94 | 0.98 |
| ford-johnson (reference) | 0.38 | 0.61 | 0.69 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 65% | 52% | 17/20 |
| **rankify-mixed** | 73% | 32% | 20/20 |
| elo | 84% | 58% | 0/20 |
| glicko2 | 84% | 57% | 0/20 |
| just-sort-it (reference) | 75% | 51% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, fuzzy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 24 · 1.1 min (20/20) | 50 · 2.3 min (16/20) | 69 · 3.5 min (18/20) |
| **rankify-mixed** | 12 · 1.2 min (19/20) | 10 · 1.2 min (20/20) | 40 · 4.5 min (14/20) |
| elo | 50 · 2.0 min (19/20) | 72 · 3.0 min (19/20) | — (6/20) |
| glicko2 | 38 · 1.7 min (19/20) | 62 · 2.6 min (17/20) | — (9/20) |
| just-sort-it (reference) | 38 · 1.7 min (19/20) | 48 · 2.3 min (19/20) | 144 · 6.6 min (13/20) |
| ford-johnson (reference) | — (9/20) | — (8/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 66 | 3.2 |
| stable | 20/20 | 15/20 | 100% of pairs right | 94 | 4.9 |
| exact | 19/20 | 15/19 | 96% of pairs right | 161 | 9.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 19/20 | 28 | 3.4 |
| stable | 20/20 | 20/20 | 100% of pairs right | 38 | 4.3 |
| exact | 20/20 | 13/20 | 95% of pairs right | 68 | 7.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 55%, stable 77%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 68%, stable 103%, exact 53%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 106%, stable 51%, exact 130%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |
| rankify-mixed | quick | 26% · 3.5 s | 7% · 3.5 s | 67% · 8.0 s |
| rankify-mixed | stable | 30% · 3.4 s | 6% · 3.6 s | 64% · 8.2 s |
| rankify-mixed | exact | 38% · 3.7 s | 3% · 3.7 s | 59% · 8.8 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 80 | 61% | 44% | 0 | 0 |
| rankify | stable | 89 | 64% | 33% | 0 | 0 |
| rankify | exact | 95 | 38% | 34% | 0 | 5 |
| rankify-mixed | quick | 52 | 56% | 46% | 0 | 0 |
| rankify-mixed | stable | 61 | 54% | 34% | 0 | 0 |
| rankify-mixed | exact | 79 | 71% | 31% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.56 | 0.82 | 0.93 | 0.96 | 0.96 |
| **rankify-mixed** | 0.84 | 0.96 | 0.96 | 0.96 | 0.96 |
| elo | 0.51 | 0.69 | 0.78 | 0.82 | 0.87 |
| glicko2 | 0.51 | 0.67 | 0.80 | 0.91 | 0.91 |
| just-sort-it (reference) | 0.53 | 0.78 | 0.89 | 0.91 | 0.91 |
| ford-johnson (reference) | 0.49 | 0.80 | 0.80 | 0.80 | 0.80 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 72% | 61% | 19/20 |
| **rankify-mixed** | 83% | 52% | 20/20 |
| elo | 89% | 77% | 0/20 |
| glicko2 | 87% | 73% | 0/20 |
| just-sort-it (reference) | 83% | 70% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, fuzzy judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 56 · 2.6 min (16/20) | 158 · 8.2 min (14/20) | — (6/20) |
| **rankify-mixed** | 16 · 2.1 min (19/20) | 72 · 9.3 min (11/20) | — (3/20) |
| elo | 194 · 8.7 min (18/20) | — (6/20) | — (0/20) |
| glicko2 | 122 · 5.2 min (18/20) | 340 · 14.8 min (12/20) | — (0/20) |
| just-sort-it (reference) | 93 · 4.2 min (19/20) | 178 · 8.3 min (15/20) | — (0/20) |
| ford-johnson (reference) | 56 · 2.6 min (12/20) | — (1/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 15/20 | #1 right in 20/20 | 88 | 3.9 |
| stable | 20/20 | 13/20 | 95% of pairs right | 190 | 9.8 |
| exact | 3/20 | 1/3 | 89% of pairs right | 379 | 22.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 34 | 4.2 |
| stable | 20/20 | 11/20 | 94% of pairs right | 72 | 10.4 |
| exact | 20/20 | 3/20 | 91% of pairs right | 156 | 21.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 30%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 62%, stable 100%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 78%, stable 113%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.4 s | 0% | 0% |
| rankify-mixed | quick | 11% · 2.9 s | 6% · 3.4 s | 83% · 8.4 s |
| rankify-mixed | stable | 18% · 3.7 s | 3% · 3.6 s | 79% · 9.3 s |
| rankify-mixed | exact | 30% · 3.9 s | 1% · 3.5 s | 69% · 9.7 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 84 | 76% | 21% | 0 | 0 |
| rankify | stable | 100 | 80% | 12% | 0 | 0 |
| rankify | exact | 15 | 7% | 42% | 0 | 85 |
| rankify-mixed | quick | 58 | 66% | 37% | 0 | 0 |
| rankify-mixed | stable | 80 | 82% | 20% | 0 | 0 |
| rankify-mixed | exact | 100 | 58% | 23% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.31 | 0.59 | 0.73 | 0.85 | 0.90 | 0.95 |
| **rankify-mixed** | 0.64 | 0.84 | 0.91 | 0.94 | 0.95 | 0.95 |
| elo | 0.33 | 0.48 | 0.61 | 0.70 | 0.82 | 0.87 |
| glicko2 | 0.32 | 0.54 | 0.65 | 0.74 | 0.86 | 0.89 |
| just-sort-it (reference) | 0.31 | 0.47 | 0.61 | 0.81 | 0.87 | 0.91 |
| ford-johnson (reference) | 0.33 | 0.55 | 0.67 | 0.82 | 0.82 | 0.82 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 85% | 74% | 3/20 |
| **rankify-mixed** | 88% | 42% | 20/20 |
| elo | 89% | 58% | 0/20 |
| glicko2 | 89% | 58% | 0/20 |
| just-sort-it (reference) | 83% | 59% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, careless judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 16 · 0.7 min (20/20) | 28 · 1.2 min (20/20) | 42 · 2.1 min (20/20) |
| **rankify-mixed** | 6 · 0.8 min (18/20) | 8 · 0.9 min (19/20) | 18 · 2.4 min (19/20) |
| elo | 61 · 2.5 min (18/20) | 88 · 3.9 min (18/20) | — (7/20) |
| glicko2 | 46 · 1.8 min (18/20) | 86 · 4.0 min (17/20) | 158 · 6.8 min (12/20) |
| just-sort-it (reference) | 34 · 1.4 min (20/20) | 38 · 1.7 min (20/20) | 76 · 3.2 min (18/20) |
| ford-johnson (reference) | 17 · 0.8 min (16/20) | 22 · 1.0 min (15/20) | — (4/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 60 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 83 | 4.6 |
| exact | 20/20 | 20/20 | 100% of pairs right | 140 | 7.6 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 18/20 | 20 | 2.3 |
| stable | 20/20 | 19/20 | 100% of pairs right | 31 | 4.0 |
| exact | 20/20 | 19/20 | 99% of pairs right | 54 | 6.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 27%, stable 30%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 48%, stable 69%, exact 64%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 122%, stable 80%, exact 115%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 20% · 3.8 s | 10% · 3.9 s | 71% · 8.2 s |
| rankify-mixed | stable | 27% · 3.9 s | 6% · 3.9 s | 67% · 8.7 s |
| rankify-mixed | exact | 36% · 4.0 s | 5% · 4.3 s | 59% · 8.8 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 74 | 50% | 59% | 0 | 0 |
| rankify | stable | 84 | 44% | 46% | 0 | 0 |
| rankify | exact | 100 | 37% | 52% | 0 | 0 |
| rankify-mixed | quick | 45 | 44% | 105% | 0 | 0 |
| rankify-mixed | stable | 57 | 46% | 67% | 0 | 0 |
| rankify-mixed | exact | 72 | 38% | 68% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.58 | 0.87 | 0.96 | 0.96 | 1.00 |
| **rankify-mixed** | 0.91 | 0.96 | 1.00 | 1.00 | 1.00 |
| elo | 0.47 | 0.62 | 0.78 | 0.87 | 0.91 |
| glicko2 | 0.51 | 0.64 | 0.82 | 0.89 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.78 | 0.91 | 0.96 | 0.96 |
| ford-johnson (reference) | 0.64 | 0.91 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 57% | 44% | 20/20 |
| **rankify-mixed** | 63% | 26% | 20/20 |
| elo | 89% | 75% | 0/20 |
| glicko2 | 88% | 73% | 0/20 |
| just-sort-it (reference) | 74% | 60% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, careless judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 50 · 2.1 min (19/20) | 81 · 3.8 min (20/20) | 178 · 10.1 min (20/20) |
| **rankify-mixed** | 14 · 1.8 min (20/20) | 26 · 3.7 min (20/20) | 54 · 8.0 min (19/20) |
| elo | 160 · 7.1 min (17/20) | 343 · 14.2 min (13/20) | — (0/20) |
| glicko2 | 102 · 4.3 min (19/20) | 286 · 12.8 min (16/20) | — (1/20) |
| just-sort-it (reference) | 89 · 4.1 min (19/20) | 154 · 7.4 min (17/20) | — (10/20) |
| ford-johnson (reference) | 46 · 2.1 min (16/20) | — (10/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 80 | 3.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 172 | 9.3 |
| exact | 16/20 | 16/16 | 100% of pairs right | 369 | 23.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 30 | 3.9 |
| stable | 20/20 | 20/20 | 100% of pairs right | 57 | 8.8 |
| exact | 20/20 | 18/20 | 99% of pairs right | 156 | 17.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 30%, stable 27%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 51%, stable 52%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 87%, stable 97%, exact 79%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-mixed | quick | 16% · 3.9 s | 7% · 3.7 s | 78% · 8.3 s |
| rankify-mixed | stable | 20% · 4.1 s | 4% · 3.8 s | 76% · 9.3 s |
| rankify-mixed | exact | 49% · 4.2 s | 2% · 4.2 s | 49% · 9.9 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 69% | 33% | 0 | 0 |
| rankify | stable | 100 | 68% | 24% | 0 | 0 |
| rankify | exact | 80 | 8% | 47% | 0 | 20 |
| rankify-mixed | quick | 53 | 55% | 48% | 0 | 0 |
| rankify-mixed | stable | 78 | 55% | 41% | 0 | 0 |
| rankify-mixed | exact | 100 | 53% | 27% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.61 | 0.82 | 0.92 | 0.97 | 0.99 |
| **rankify-mixed** | 0.70 | 0.92 | 0.96 | 0.97 | 0.98 | 0.99 |
| elo | 0.41 | 0.53 | 0.66 | 0.75 | 0.81 | 0.88 |
| glicko2 | 0.40 | 0.53 | 0.72 | 0.81 | 0.86 | 0.92 |
| just-sort-it (reference) | 0.28 | 0.46 | 0.67 | 0.85 | 0.94 | 0.96 |
| ford-johnson (reference) | 0.38 | 0.58 | 0.70 | 0.89 | 0.89 | 0.89 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 70% | 54% | 16/20 |
| **rankify-mixed** | 75% | 29% | 20/20 |
| elo | 87% | 58% | 0/20 |
| glicko2 | 87% | 58% | 0/20 |
| just-sort-it (reference) | 80% | 56% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, biased judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 22 · 0.9 min (20/20) | 25 · 1.1 min (20/20) | 39 · 1.9 min (19/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 7 · 0.7 min (20/20) | 12 · 1.3 min (19/20) |
| elo | 48 · 1.9 min (20/20) | 64 · 2.8 min (19/20) | — (10/20) |
| glicko2 | 33 · 1.4 min (20/20) | 49 · 1.9 min (20/20) | 91 · 3.7 min (19/20) |
| just-sort-it (reference) | 25 · 1.0 min (20/20) | 32 · 1.4 min (20/20) | 56 · 2.4 min (20/20) |
| ford-johnson (reference) | 22 · 1.0 min (14/20) | 22 · 1.0 min (13/20) | — (7/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 58 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 78 | 4.2 |
| exact | 20/20 | 19/20 | 99% of pairs right | 140 | 7.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 18 | 2.0 |
| stable | 20/20 | 20/20 | 100% of pairs right | 31 | 3.5 |
| exact | 20/20 | 19/20 | 99% of pairs right | 59 | 6.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 48%, stable 39%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 87%, stable 78%, exact 81%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 65%, stable 62%, exact 68%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 25% · 4.2 s | 9% · 3.5 s | 65% · 7.8 s |
| rankify-mixed | stable | 34% · 3.9 s | 6% · 3.5 s | 59% · 8.5 s |
| rankify-mixed | exact | 38% · 4.2 s | 5% · 3.9 s | 57% · 8.7 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 74 | 47% | 64% | 0 | 0 |
| rankify | stable | 84 | 42% | 54% | 0 | 0 |
| rankify | exact | 100 | 32% | 52% | 0 | 0 |
| rankify-mixed | quick | 46 | 48% | 100% | 0 | 0 |
| rankify-mixed | stable | 56 | 52% | 70% | 0 | 0 |
| rankify-mixed | exact | 76 | 62% | 51% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.58 | 0.93 | 0.98 | 1.00 | 1.00 |
| **rankify-mixed** | 0.96 | 0.98 | 0.98 | 1.00 | 1.00 |
| elo | 0.56 | 0.73 | 0.82 | 0.91 | 0.91 |
| glicko2 | 0.56 | 0.78 | 0.87 | 0.96 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.84 | 0.96 | 0.96 | 1.00 |
| ford-johnson (reference) | 0.62 | 0.91 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 51% | 40% | 20/20 |
| **rankify-mixed** | 47% | 21% | 20/20 |
| elo | 84% | 72% | 0/20 |
| glicko2 | 77% | 61% | 0/20 |
| just-sort-it (reference) | 61% | 45% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, biased judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 37 · 1.6 min (19/20) | 74 · 3.4 min (19/20) | 144 · 8.0 min (20/20) |
| **rankify-mixed** | 14 · 1.8 min (19/20) | 22 · 3.3 min (20/20) | 52 · 6.8 min (20/20) |
| elo | 180 · 8.2 min (16/20) | 367 · 16.7 min (12/20) | — (1/20) |
| glicko2 | 85 · 3.8 min (18/20) | 274 · 11.3 min (14/20) | — (2/20) |
| just-sort-it (reference) | 86 · 3.9 min (19/20) | 108 · 5.3 min (19/20) | 328 · 15.9 min (12/20) |
| ford-johnson (reference) | 31 · 1.4 min (17/20) | — (10/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 20/20 | 68 | 3.1 |
| stable | 20/20 | 19/20 | 100% of pairs right | 168 | 8.8 |
| exact | 18/20 | 18/18 | 100% of pairs right | 363 | 23.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 27 | 3.3 |
| stable | 20/20 | 20/20 | 100% of pairs right | 55 | 8.4 |
| exact | 20/20 | 20/20 | 100% of pairs right | 156 | 17.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 19%, stable 21%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 41%, stable 64%, exact 50%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 115%, stable 95%, exact 85%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-mixed | quick | 13% · 3.8 s | 7% · 3.3 s | 80% · 8.4 s |
| rankify-mixed | stable | 20% · 3.9 s | 5% · 3.5 s | 76% · 9.5 s |
| rankify-mixed | exact | 57% · 4.2 s | 2% · 4.4 s | 41% · 9.6 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 80 | 51% | 63% | 0 | 0 |
| rankify | stable | 100 | 50% | 30% | 0 | 0 |
| rankify | exact | 90 | 12% | 47% | 0 | 10 |
| rankify-mixed | quick | 51 | 43% | 83% | 0 | 0 |
| rankify-mixed | stable | 75 | 56% | 38% | 0 | 0 |
| rankify-mixed | exact | 100 | 59% | 25% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.36 | 0.64 | 0.82 | 0.94 | 0.97 | 0.99 |
| **rankify-mixed** | 0.71 | 0.93 | 0.95 | 0.98 | 0.98 | 0.98 |
| elo | 0.40 | 0.53 | 0.65 | 0.74 | 0.84 | 0.91 |
| glicko2 | 0.39 | 0.56 | 0.72 | 0.81 | 0.89 | 0.94 |
| just-sort-it (reference) | 0.27 | 0.46 | 0.66 | 0.91 | 0.95 | 0.97 |
| ford-johnson (reference) | 0.38 | 0.58 | 0.69 | 0.90 | 0.90 | 0.90 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 62% | 48% | 18/20 |
| **rankify-mixed** | 69% | 26% | 20/20 |
| elo | 84% | 58% | 0/20 |
| glicko2 | 84% | 58% | 0/20 |
| just-sort-it (reference) | 76% | 53% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, thurstone judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 19 · 0.8 min (20/20) | 24 · 1.0 min (20/20) | 38 · 1.9 min (20/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 8 · 0.8 min (20/20) | 11 · 1.5 min (20/20) |
| elo | 48 · 2.0 min (20/20) | 73 · 3.1 min (20/20) | — (10/20) |
| glicko2 | 36 · 1.5 min (20/20) | 50 · 2.0 min (20/20) | 92 · 3.7 min (16/20) |
| just-sort-it (reference) | 24 · 1.0 min (20/20) | 28 · 1.4 min (20/20) | 56 · 2.6 min (19/20) |
| ford-johnson (reference) | 21 · 0.9 min (15/20) | 22 · 1.0 min (13/20) | — (8/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 50 | 2.4 |
| stable | 20/20 | 20/20 | 100% of pairs right | 77 | 4.3 |
| exact | 20/20 | 19/20 | 99% of pairs right | 160 | 8.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 18 | 2.2 |
| stable | 20/20 | 20/20 | 100% of pairs right | 26 | 3.2 |
| exact | 20/20 | 20/20 | 100% of pairs right | 55 | 6.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 39%, stable 33%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 79%, stable 73%, exact 73%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 82%, stable 80%, exact 77%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-mixed | quick | 24% · 4.4 s | 10% · 3.5 s | 66% · 8.0 s |
| rankify-mixed | stable | 27% · 4.0 s | 7% · 3.5 s | 66% · 8.7 s |
| rankify-mixed | exact | 35% · 4.1 s | 4% · 3.5 s | 61% · 8.9 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 72 | 40% | 81% | 0 | 0 |
| rankify | stable | 83 | 45% | 51% | 0 | 0 |
| rankify | exact | 100 | 33% | 41% | 0 | 0 |
| rankify-mixed | quick | 44 | 41% | 115% | 0 | 0 |
| rankify-mixed | stable | 53 | 40% | 100% | 0 | 0 |
| rankify-mixed | exact | 76 | 58% | 56% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.93 | 0.96 | 1.00 | 1.00 |
| **rankify-mixed** | 0.96 | 1.00 | 0.98 | 0.96 | 0.96 |
| elo | 0.56 | 0.73 | 0.80 | 0.87 | 0.91 |
| glicko2 | 0.53 | 0.78 | 0.87 | 0.96 | 0.96 |
| just-sort-it (reference) | 0.56 | 0.87 | 0.96 | 0.96 | 0.98 |
| ford-johnson (reference) | 0.62 | 0.96 | 0.96 | 0.96 | 0.96 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 48% | 38% | 20/20 |
| **rankify-mixed** | 44% | 14% | 20/20 |
| elo | 85% | 73% | 0/20 |
| glicko2 | 79% | 64% | 0/20 |
| just-sort-it (reference) | 64% | 50% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, thurstone judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 40 · 1.8 min (20/20) | 74 · 3.7 min (20/20) | 144 · 8.0 min (20/20) |
| **rankify-mixed** | 13 · 1.6 min (20/20) | 18 · 2.6 min (20/20) | 60 · 7.9 min (20/20) |
| elo | 204 · 9.0 min (16/20) | 354 · 15.6 min (12/20) | — (1/20) |
| glicko2 | 124 · 5.2 min (18/20) | 265 · 11.7 min (15/20) | — (3/20) |
| just-sort-it (reference) | 98 · 4.6 min (20/20) | 117 · 5.4 min (20/20) | 309 · 14.7 min (14/20) |
| ford-johnson (reference) | 30 · 1.4 min (16/20) | — (10/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 67 | 3.2 |
| stable | 20/20 | 20/20 | 100% of pairs right | 166 | 8.8 |
| exact | 18/20 | 18/18 | 100% of pairs right | 366 | 23.3 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 27 | 3.4 |
| stable | 20/20 | 20/20 | 100% of pairs right | 58 | 7.6 |
| exact | 20/20 | 18/20 | 99% of pairs right | 154 | 17.4 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 20%, stable 24%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 38%, stable 68%, exact 54%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 94%, stable 70%, exact 99%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-mixed | quick | 11% · 3.6 s | 7% · 3.4 s | 81% · 8.7 s |
| rankify-mixed | stable | 21% · 4.0 s | 4% · 3.4 s | 75% · 9.5 s |
| rankify-mixed | exact | 57% · 4.2 s | 2% · 4.2 s | 41% · 9.6 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 48% | 64% | 0 | 0 |
| rankify | stable | 100 | 58% | 27% | 0 | 0 |
| rankify | exact | 90 | 12% | 46% | 0 | 10 |
| rankify-mixed | quick | 55 | 36% | 74% | 0 | 0 |
| rankify-mixed | stable | 74 | 64% | 39% | 0 | 0 |
| rankify-mixed | exact | 100 | 62% | 27% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.64 | 0.84 | 0.94 | 0.97 | 0.98 |
| **rankify-mixed** | 0.73 | 0.94 | 0.96 | 0.97 | 0.98 | 0.98 |
| elo | 0.40 | 0.54 | 0.64 | 0.75 | 0.84 | 0.89 |
| glicko2 | 0.39 | 0.56 | 0.71 | 0.81 | 0.89 | 0.94 |
| just-sort-it (reference) | 0.27 | 0.44 | 0.69 | 0.89 | 0.95 | 0.97 |
| ford-johnson (reference) | 0.38 | 0.59 | 0.71 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 59% | 45% | 18/20 |
| **rankify-mixed** | 68% | 22% | 20/20 |
| elo | 84% | 58% | 0/20 |
| glicko2 | 83% | 57% | 0/20 |
| just-sort-it (reference) | 75% | 51% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, similar judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 18 · 0.8 min (20/20) | 20 · 0.9 min (20/20) | 32 · 1.4 min (20/20) |
| **rankify-mixed** | 6 · 0.7 min (20/20) | 8 · 0.9 min (20/20) | 11 · 1.2 min (20/20) |
| elo | 44 · 2.0 min (20/20) | 56 · 2.3 min (20/20) | 152 · 6.2 min (12/20) |
| glicko2 | 35 · 1.6 min (20/20) | 41 · 1.8 min (20/20) | 108 · 5.0 min (16/20) |
| just-sort-it (reference) | 31 · 1.3 min (20/20) | 33 · 1.6 min (20/20) | 54 · 2.4 min (20/20) |
| ford-johnson (reference) | 22 · 1.0 min (15/20) | 22 · 1.0 min (13/20) | — (9/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 19/20 | 56 | 2.9 |
| stable | 20/20 | 20/20 | 100% of pairs right | 102 | 6.2 |
| exact | 19/20 | 19/19 | 100% of pairs right | 160 | 9.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 21 | 2.4 |
| stable | 20/20 | 20/20 | 100% of pairs right | 34 | 4.4 |
| exact | 20/20 | 20/20 | 100% of pairs right | 61 | 7.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 41%, stable 37%, exact 23%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 63%, stable 55%, exact 59%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 91%, stable 99%, exact 87%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.7 s | 0% | 0% |
| rankify | stable | 100% · 3.1 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |
| rankify-mixed | quick | 24% · 4.4 s | 9% · 3.5 s | 67% · 8.8 s |
| rankify-mixed | stable | 33% · 4.3 s | 6% · 3.5 s | 61% · 8.9 s |
| rankify-mixed | exact | 37% · 4.4 s | 4% · 3.5 s | 59% · 8.8 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 73 | 48% | 65% | 0 | 0 |
| rankify | stable | 92 | 65% | 25% | 0 | 0 |
| rankify | exact | 97 | 38% | 39% | 0 | 3 |
| rankify-mixed | quick | 46 | 37% | 99% | 0 | 0 |
| rankify-mixed | stable | 59 | 46% | 55% | 0 | 0 |
| rankify-mixed | exact | 75 | 60% | 47% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.62 | 0.91 | 0.93 | 0.96 | 0.96 |
| **rankify-mixed** | 0.91 | 0.96 | 0.96 | 0.96 | 0.96 |
| elo | 0.51 | 0.67 | 0.82 | 0.91 | 0.91 |
| glicko2 | 0.53 | 0.78 | 0.87 | 0.96 | 0.96 |
| just-sort-it (reference) | 0.53 | 0.80 | 0.91 | 0.91 | 0.96 |
| ford-johnson (reference) | 0.62 | 0.91 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 49% | 38% | 19/20 |
| **rankify-mixed** | 33% | 4% | 20/20 |
| elo | 85% | 71% | 0/20 |
| glicko2 | 82% | 67% | 0/20 |
| just-sort-it (reference) | 67% | 50% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, similar judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 44 · 1.9 min (19/20) | 73 · 3.4 min (20/20) | 167 · 9.7 min (20/20) |
| **rankify-mixed** | 14 · 1.8 min (20/20) | 22 · 3.1 min (20/20) | 61 · 8.5 min (20/20) |
| elo | 132 · 5.8 min (19/20) | 346 · 15.8 min (11/20) | — (1/20) |
| glicko2 | 102 · 4.6 min (20/20) | 288 · 12.3 min (17/20) | — (3/20) |
| just-sort-it (reference) | 79 · 3.9 min (20/20) | 120 · 6.1 min (19/20) | 214 · 10.7 min (15/20) |
| ford-johnson (reference) | 44 · 2.0 min (15/20) | — (9/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 20/20 | 78 | 3.9 |
| stable | 20/20 | 20/20 | 100% of pairs right | 182 | 10.3 |
| exact | 11/20 | 11/11 | 100% of pairs right | 369 | 25.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 34 | 4.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 66 | 9.6 |
| exact | 20/20 | 18/20 | 100% of pairs right | 162 | 19.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 33%, stable 22%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 50%, stable 56%, exact 90%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 92%, stable 92%, exact 88%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 3.2 s | 0% | 0% |
| rankify | exact | 100% · 3.8 s | 0% | 0% |
| rankify-mixed | quick | 13% · 4.5 s | 6% · 3.4 s | 81% · 9.2 s |
| rankify-mixed | stable | 22% · 4.5 s | 4% · 3.6 s | 74% · 9.9 s |
| rankify-mixed | exact | 54% · 4.4 s | 2% · 4.0 s | 44% · 10.0 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 84 | 68% | 33% | 0 | 0 |
| rankify | stable | 100 | 72% | 19% | 0 | 0 |
| rankify | exact | 55 | 5% | 45% | 0 | 45 |
| rankify-mixed | quick | 58 | 59% | 43% | 0 | 0 |
| rankify-mixed | stable | 78 | 69% | 23% | 0 | 0 |
| rankify-mixed | exact | 100 | 64% | 23% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.29 | 0.63 | 0.83 | 0.92 | 0.96 | 0.97 |
| **rankify-mixed** | 0.75 | 0.92 | 0.95 | 0.96 | 0.96 | 0.96 |
| elo | 0.32 | 0.52 | 0.65 | 0.74 | 0.84 | 0.92 |
| glicko2 | 0.33 | 0.53 | 0.69 | 0.80 | 0.89 | 0.94 |
| just-sort-it (reference) | 0.32 | 0.37 | 0.69 | 0.88 | 0.93 | 0.96 |
| ford-johnson (reference) | 0.37 | 0.56 | 0.66 | 0.89 | 0.89 | 0.89 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 64% | 50% | 11/20 |
| **rankify-mixed** | 76% | 34% | 20/20 |
| elo | 85% | 58% | 0/20 |
| glicko2 | 85% | 57% | 0/20 |
| just-sort-it (reference) | 73% | 50% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 10 items, tired judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 20 · 0.8 min (20/20) | 25 · 1.1 min (20/20) | 58 · 3.2 min (19/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 7 · 0.7 min (20/20) | 14 · 1.5 min (20/20) |
| elo | 46 · 1.9 min (20/20) | 72 · 3.2 min (19/20) | — (7/20) |
| glicko2 | 34 · 1.4 min (20/20) | 47 · 1.9 min (20/20) | 147 · 5.9 min (12/20) |
| just-sort-it (reference) | 25 · 1.0 min (20/20) | 34 · 1.5 min (20/20) | 70 · 3.0 min (16/20) |
| ford-johnson (reference) | 22 · 1.0 min (13/20) | 22 · 1.0 min (12/20) | — (5/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 58 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 80 | 4.2 |
| exact | 20/20 | 18/20 | 99% of pairs right | 152 | 8.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 16 | 1.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 30 | 3.5 |
| exact | 20/20 | 19/20 | 99% of pairs right | 60 | 7.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 44%, stable 33%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 80%, stable 73%, exact 106%
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 69%, stable 66%, exact 47%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.2 s | 0% | 0% |
| rankify-mixed | quick | 20% · 4.0 s | 10% · 3.5 s | 70% · 7.9 s |
| rankify-mixed | stable | 30% · 3.6 s | 6% · 3.5 s | 64% · 8.2 s |
| rankify-mixed | exact | 36% · 4.0 s | 4% · 3.5 s | 60% · 8.7 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 74 | 42% | 64% | 0 | 0 |
| rankify | stable | 86 | 51% | 45% | 0 | 0 |
| rankify | exact | 100 | 40% | 40% | 0 | 0 |
| rankify-mixed | quick | 45 | 42% | 144% | 0 | 0 |
| rankify-mixed | stable | 58 | 48% | 77% | 0 | 0 |
| rankify-mixed | exact | 77 | 65% | 46% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.91 | 0.96 | 0.96 | 1.00 |
| **rankify-mixed** | 0.91 | 0.96 | 0.98 | 1.00 | 1.00 |
| elo | 0.56 | 0.73 | 0.80 | 0.89 | 0.87 |
| glicko2 | 0.53 | 0.78 | 0.87 | 0.93 | 0.91 |
| just-sort-it (reference) | 0.56 | 0.82 | 0.96 | 0.96 | 0.96 |
| ford-johnson (reference) | 0.60 | 0.91 | 0.91 | 0.91 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 64% | 55% | 20/20 |
| **rankify-mixed** | 54% | 21% | 20/20 |
| elo | 87% | 75% | 0/20 |
| glicko2 | 83% | 70% | 0/20 |
| just-sort-it (reference) | 74% | 60% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## 20 items, tired judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 38 · 1.6 min (18/20) | 88 · 4.2 min (18/20) | — (10/20) |
| **rankify-mixed** | 16 · 2.0 min (19/20) | 21 · 2.9 min (19/20) | — (7/20) |
| elo | 199 · 8.4 min (18/20) | — (10/20) | — (0/20) |
| glicko2 | 116 · 5.2 min (19/20) | 368 · 16.5 min (11/20) | — (0/20) |
| just-sort-it (reference) | 88 · 4.1 min (20/20) | 166 · 7.8 min (18/20) | — (2/20) |
| ford-johnson (reference) | 31 · 1.4 min (15/20) | — (7/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 18/20 | #1 right in 20/20 | 78 | 3.7 |
| stable | 20/20 | 15/20 | 95% of pairs right | 190 | 10.5 |
| exact | 6/20 | 2/6 | 94% of pairs right | 388 | 22.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-mixed stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 34 | 4.5 |
| stable | 20/20 | 19/20 | 98% of pairs right | 62 | 9.5 |
| exact | 20/20 | 5/20 | 90% of pairs right | 172 | 21.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of elo's (G1: at most 50%): quick 19%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 40%, stable 54%, exact n/a
- rankify-mixed's time as a share of rankify's (G3: under 100%): quick 125%, stable 68%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.5 s | 0% | 0% |
| rankify-mixed | quick | 15% · 3.9 s | 6% · 3.4 s | 78% · 8.5 s |
| rankify-mixed | stable | 18% · 3.9 s | 4% · 3.7 s | 78% · 9.6 s |
| rankify-mixed | exact | 44% · 3.8 s | 2% · 4.5 s | 53% · 9.8 s |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 58% | 36% | 0 | 0 |
| rankify | stable | 100 | 82% | 10% | 0 | 0 |
| rankify | exact | 30 | 17% | 40% | 0 | 70 |
| rankify-mixed | quick | 54 | 61% | 40% | 0 | 0 |
| rankify-mixed | stable | 78 | 76% | 28% | 0 | 0 |
| rankify-mixed | exact | 100 | 56% | 25% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.64 | 0.83 | 0.91 | 0.94 | 0.95 |
| **rankify-mixed** | 0.70 | 0.90 | 0.92 | 0.93 | 0.94 | 0.94 |
| elo | 0.40 | 0.51 | 0.63 | 0.74 | 0.82 | 0.84 |
| glicko2 | 0.39 | 0.55 | 0.68 | 0.77 | 0.87 | 0.88 |
| just-sort-it (reference) | 0.27 | 0.44 | 0.67 | 0.84 | 0.91 | 0.90 |
| ford-johnson (reference) | 0.38 | 0.61 | 0.69 | 0.88 | 0.88 | 0.88 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 80% | 71% | 6/20 |
| **rankify-mixed** | 87% | 48% | 20/20 |
| elo | 86% | 58% | 0/20 |
| glicko2 | 86% | 58% | 0/20 |
| just-sort-it (reference) | 81% | 58% | 0/20 |
| ford-johnson (reference) | 0% | 0% | 20/20 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 10 | human | 0.043 | 98% |
| **rankify** | 10 | perfect | 0.038 | 100% |
| **rankify** | 10 | noisy | 0.042 | 98% |
| **rankify** | 10 | sharp | 0.027 | 98% |
| **rankify** | 10 | normal | 0.020 | 98% |
| **rankify** | 10 | fuzzy | 0.018 | 98% |
| **rankify** | 10 | careless | 0.026 | 99% |
| **rankify** | 10 | biased | 0.026 | 100% |
| **rankify** | 10 | thurstone | 0.038 | 100% |
| **rankify** | 10 | similar | 0.036 | 96% |
| **rankify** | 10 | tired | 0.037 | 98% |
| **rankify** | 20 | human | 0.048 | 88% |
| **rankify** | 20 | perfect | 0.039 | 100% |
| **rankify** | 20 | noisy | 0.029 | 96% |
| **rankify** | 20 | sharp | 0.031 | 100% |
| **rankify** | 20 | normal | 0.037 | 100% |
| **rankify** | 20 | fuzzy | 0.038 | 97% |
| **rankify** | 20 | careless | 0.051 | 99% |
| **rankify** | 20 | biased | 0.034 | 100% |
| **rankify** | 20 | thurstone | 0.031 | 99% |
| **rankify** | 20 | similar | 0.050 | 98% |
| **rankify** | 20 | tired | 0.014 | 95% |
| **rankify-mixed** | 10 | human | 0.047 | 96% |
| **rankify-mixed** | 10 | perfect | 0.038 | 100% |
| **rankify-mixed** | 10 | noisy | 0.028 | 98% |
| **rankify-mixed** | 10 | sharp | 0.020 | 99% |
| **rankify-mixed** | 10 | normal | 0.023 | 100% |
| **rankify-mixed** | 10 | fuzzy | 0.045 | 100% |
| **rankify-mixed** | 10 | careless | 0.023 | 99% |
| **rankify-mixed** | 10 | biased | 0.026 | 99% |
| **rankify-mixed** | 10 | thurstone | 0.055 | 100% |
| **rankify-mixed** | 10 | similar | 0.042 | 98% |
| **rankify-mixed** | 10 | tired | 0.026 | 100% |
| **rankify-mixed** | 20 | human | 0.023 | 93% |
| **rankify-mixed** | 20 | perfect | 0.033 | 100% |
| **rankify-mixed** | 20 | noisy | 0.044 | 98% |
| **rankify-mixed** | 20 | sharp | 0.026 | 100% |
| **rankify-mixed** | 20 | normal | 0.036 | 99% |
| **rankify-mixed** | 20 | fuzzy | 0.039 | 98% |
| **rankify-mixed** | 20 | careless | 0.039 | 100% |
| **rankify-mixed** | 20 | biased | 0.029 | 99% |
| **rankify-mixed** | 20 | thurstone | 0.037 | 99% |
| **rankify-mixed** | 20 | similar | 0.026 | 97% |
| **rankify-mixed** | 20 | tired | 0.036 | 95% |
| glicko2 | 10 | human | 0.045 | 98% |
| glicko2 | 10 | perfect | 0.151 | 100% |
| glicko2 | 10 | noisy | 0.045 | 97% |
| glicko2 | 10 | sharp | 0.092 | 100% |
| glicko2 | 10 | normal | 0.081 | 100% |
| glicko2 | 10 | fuzzy | 0.062 | 98% |
| glicko2 | 10 | careless | 0.091 | 100% |
| glicko2 | 10 | biased | 0.075 | 100% |
| glicko2 | 10 | thurstone | 0.072 | 100% |
| glicko2 | 10 | similar | 0.056 | 99% |
| glicko2 | 10 | tired | 0.069 | 98% |
| glicko2 | 20 | human | 0.030 | 96% |
| glicko2 | 20 | perfect | 0.121 | 100% |
| glicko2 | 20 | noisy | 0.041 | 97% |
| glicko2 | 20 | sharp | 0.091 | 100% |
| glicko2 | 20 | normal | 0.076 | 99% |
| glicko2 | 20 | fuzzy | 0.048 | 98% |
| glicko2 | 20 | careless | 0.062 | 99% |
| glicko2 | 20 | biased | 0.085 | 99% |
| glicko2 | 20 | thurstone | 0.078 | 99% |
| glicko2 | 20 | similar | 0.079 | 100% |
| glicko2 | 20 | tired | 0.041 | 98% |
| just-sort-it (reference) | 10 | human | 0.040 | 98% |
| just-sort-it (reference) | 10 | perfect | 0.030 | 100% |
| just-sort-it (reference) | 10 | noisy | 0.051 | 99% |
| just-sort-it (reference) | 10 | sharp | 0.034 | 100% |
| just-sort-it (reference) | 10 | normal | 0.052 | 100% |
| just-sort-it (reference) | 10 | fuzzy | 0.029 | 98% |
| just-sort-it (reference) | 10 | careless | 0.049 | 100% |
| just-sort-it (reference) | 10 | biased | 0.057 | 100% |
| just-sort-it (reference) | 10 | thurstone | 0.042 | 100% |
| just-sort-it (reference) | 10 | similar | 0.041 | 100% |
| just-sort-it (reference) | 10 | tired | 0.034 | 98% |
| just-sort-it (reference) | 20 | human | 0.028 | 96% |
| just-sort-it (reference) | 20 | perfect | 0.053 | 100% |
| just-sort-it (reference) | 20 | noisy | 0.023 | 98% |
| just-sort-it (reference) | 20 | sharp | 0.042 | 99% |
| just-sort-it (reference) | 20 | normal | 0.048 | 100% |
| just-sort-it (reference) | 20 | fuzzy | 0.051 | 96% |
| just-sort-it (reference) | 20 | careless | 0.059 | 99% |
| just-sort-it (reference) | 20 | biased | 0.053 | 100% |
| just-sort-it (reference) | 20 | thurstone | 0.036 | 100% |
| just-sort-it (reference) | 20 | similar | 0.024 | 98% |
| just-sort-it (reference) | 20 | tired | 0.041 | 96% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/440 lists; median τ between the two rankings 1.00
- rankify-mixed: #1 changed in 0/440 lists; median τ between the two rankings 1.00
- elo: #1 changed in 44/440 lists; median τ between the two rankings 0.96
- glicko2: #1 changed in 6/440 lists; median τ between the two rankings 0.97

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 3.5 | 3.9 | 1.4 |
| **rankify-mixed** | 5.6 | 4.4 | 1.5 |
| elo | 1.4 | 2.1 | 1.3 |
| glicko2 | 1.4 | 3.5 | 1.4 |
| just-sort-it (reference) | 2.0 | 4.3 | 1.4 |
| ford-johnson (reference) | 1.6 | 3.5 | 1.4 |

A real `rankify` subprocess (20 items, includes Python start-up): next 917 ms, answer 75 ms, show 72 ms.

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
