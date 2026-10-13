# Benchmark: rankify against rating systems for human judges

- Date: 2026-10-12 11:36 UTC
- Code: commit fef1db1 + uncommitted changes, engine 0.3.0
- Setup: 10, 20 items; judges: human, normal, careless; 20 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 720 s for 720 runs; the other 360 came from the cache.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify as shipped (pairs); rankify-mixed (the same with `new --rounds mixed`, which also asks picks and rankings of 3 to 5 items); when run, two planner variants that check rankify's design (rankify-closest asks the relevant pair closest to 50/50, rankify-per-round counts information per round, not per second; both stop by rankify's rules); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and three sorts as reference lines only (Just Sort It, binary insertion, and Ford–Johnson merge insertion, which needs the fewest comparisons). The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes, as accurate as the human judge. **sharp**, **normal**, **fuzzy**: the model rankify assumes, telling neighbours on a 20-item list apart 90%, 75% and 60% of the time. The rest are normal with one twist: **careless** answers 5% at random; **biased** favours the item shown first (60% between equals); **thurstone** has normal-curve noise; **similar** gives a quarter of the items a near-identical twin, and twins shown together in a pick or ordering split one option's chance (Debreu 1960); **tired** gets 1% noisier every round.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 67% | 7% | 3.3 |
| normal | 77% | 0% | 3.8 |
| careless | 77% | 0% | 3.7 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 39 · 1.8 min (16/20) | 73 · 3.3 min (14/20) | — (10/20) |
| **rankify-closest** | 25 · 1.3 min (14/20) | — (9/20) | — (9/20) |
| **rankify-per-round** | 42 · 2.1 min (15/20) | 49 · 2.2 min (16/20) | — (10/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 15/20 | #1 right in 17/20 | 84 | 4.0 |
| stable | 20/20 | 14/20 | 92% of pairs right | 116 | 5.9 |
| exact | 9/20 | 5/9 | 94% of pairs right | 172 | 8.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 2/20 | 2/2 | #1 right in 2/2 | 62 | 2.6 |
| stable | 0/20 | 0/0 | — | — | — |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 13/20 | #1 right in 17/20 | 82 | 4.2 |
| stable | 20/20 | 13/20 | 95% of pairs right | 115 | 6.1 |
| exact | 14/20 | 5/14 | 91% of pairs right | 182 | 9.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick 145%, stable n/a, exact n/a
- rankify's time as a share of rankify-per-round's (per second against per round): quick 86%, stable 152%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.0 s | 0% | 0% |
| rankify-closest | quick | 100% · 3.2 s | 0% | 0% |
| rankify-closest | stable | 100% · 3.6 s | 0% | 0% |
| rankify-closest | exact | 100% · 3.7 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.7 s | 0% | 0% |
| rankify-per-round | stable | 100% · 2.8 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 84 | 68% | 20% | 0 | 0 |
| rankify | stable | 94 | 73% | 16% | 0 | 0 |
| rankify | exact | 45 | 51% | 24% | 0 | 55 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.49 | 0.80 | 0.82 | 0.89 | 0.91 |
| **rankify-closest** | 0.56 | 0.76 | 0.87 | 0.91 | 0.93 |
| **rankify-per-round** | 0.49 | 0.76 | 0.87 | 0.89 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 86% | 78% | 9/20 |
| **rankify-closest** | 85% | 81% | 0/20 |
| **rankify-per-round** | 86% | 78% | 14/20 |

## 20 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 74 · 3.4 min (12/20) | — (5/20) | — (0/20) |
| **rankify-closest** | — (6/20) | — (0/20) | — (0/20) |
| **rankify-per-round** | 81 · 3.2 min (11/20) | — (7/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 10/20 | #1 right in 19/20 | 90 | 3.9 |
| stable | 20/20 | 4/20 | 85% of pairs right | 199 | 10.1 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 4/20 | 1/4 | #1 right in 4/4 | 110 | 4.6 |
| stable | 3/20 | 0/3 | 82% of pairs right | 139 | 9.0 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 10/20 | #1 right in 19/20 | 88 | 3.8 |
| stable | 20/20 | 4/20 | 85% of pairs right | 200 | 10.1 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick n/a, stable n/a, exact n/a
- rankify's time as a share of rankify-per-round's (per second against per round): quick 104%, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 2.7 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-closest | quick | 100% · 2.7 s | 0% | 0% |
| rankify-closest | stable | 100% · 3.2 s | 0% | 0% |
| rankify-closest | exact | 100% · 3.5 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.4 s | 0% | 0% |
| rankify-per-round | stable | 100% · 2.8 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 85 | 81% | 16% | 0 | 0 |
| rankify | stable | 100 | 72% | 18% | 0 | 0 |
| rankify | exact | 0 | — | — | 0 | 100 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.26 | 0.54 | 0.68 | 0.79 | 0.83 | 0.86 |
| **rankify-closest** | 0.29 | 0.49 | 0.67 | 0.77 | 0.82 | 0.86 |
| **rankify-per-round** | 0.26 | 0.54 | 0.65 | 0.79 | 0.82 | 0.85 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 87% | 73% | 0/20 |
| **rankify-closest** | 87% | 78% | 0/20 |
| **rankify-per-round** | 87% | 74% | 0/20 |

## 10 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 20 · 0.9 min (20/20) | 24 · 1.0 min (20/20) | 40 · 1.9 min (20/20) |
| **rankify-closest** | 18 · 0.8 min (20/20) | 25 · 1.2 min (19/20) | 32 · 1.7 min (20/20) |
| **rankify-per-round** | 21 · 0.9 min (20/20) | 22 · 1.0 min (20/20) | 37 · 1.7 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 54 | 2.6 |
| stable | 20/20 | 20/20 | 100% of pairs right | 77 | 4.1 |
| exact | 20/20 | 20/20 | 100% of pairs right | 146 | 8.1 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 9/20 | 9/9 | #1 right in 9/9 | 49 | 2.3 |
| stable | 4/20 | 4/4 | 100% of pairs right | 92 | 4.7 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 56 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 79 | 4.1 |
| exact | 20/20 | 20/20 | 100% of pairs right | 145 | 7.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick 115%, stable 88%, exact 114%
- rankify's time as a share of rankify-per-round's (per second against per round): quick 99%, stable 105%, exact 111%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.8 s | 0% | 0% |
| rankify | exact | 100% · 3.0 s | 0% | 0% |
| rankify-closest | quick | 100% · 4.1 s | 0% | 0% |
| rankify-closest | stable | 100% · 4.1 s | 0% | 0% |
| rankify-closest | exact | 100% · 4.3 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.7 s | 0% | 0% |
| rankify-per-round | stable | 100% · 2.9 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.1 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 73 | 42% | 79% | 0 | 0 |
| rankify | stable | 83 | 43% | 56% | 0 | 0 |
| rankify | exact | 100 | 32% | 48% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.93 | 0.98 | 1.00 | 1.00 |
| **rankify-closest** | 0.64 | 0.91 | 1.00 | 1.00 | 1.00 |
| **rankify-per-round** | 0.60 | 0.93 | 0.98 | 0.98 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 50% | 40% | 20/20 |
| **rankify-closest** | 33% | 28% | 0/20 |
| **rankify-per-round** | 44% | 35% | 20/20 |

## 20 items, normal judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 42 · 1.8 min (20/20) | 79 · 3.8 min (19/20) | 168 · 9.5 min (20/20) |
| **rankify-closest** | 44 · 2.1 min (17/20) | — (6/20) | 202 · 13.0 min (13/20) |
| **rankify-per-round** | 36 · 1.6 min (20/20) | 80 · 3.6 min (20/20) | 167 · 9.4 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 66 | 3.0 |
| stable | 20/20 | 19/20 | 100% of pairs right | 175 | 9.5 |
| exact | 17/20 | 17/17 | 100% of pairs right | 365 | 23.3 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 11/20 | 10/11 | #1 right in 11/11 | 92 | 3.6 |
| stable | 3/20 | 1/3 | 100% of pairs right | 117 | 5.1 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 70 | 3.1 |
| stable | 20/20 | 18/20 | 100% of pairs right | 166 | 9.2 |
| exact | 20/20 | 19/20 | 100% of pairs right | 359 | 22.5 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick 85%, stable n/a, exact 73%
- rankify's time as a share of rankify-per-round's (per second against per round): quick 109%, stable 104%, exact 101%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.4 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-closest | quick | 100% · 3.9 s | 0% | 0% |
| rankify-closest | stable | 100% · 4.2 s | 0% | 0% |
| rankify-closest | exact | 100% · 4.3 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.5 s | 0% | 0% |
| rankify-per-round | stable | 100% · 3.1 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.7 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 44% | 67% | 0 | 0 |
| rankify | stable | 100 | 65% | 21% | 0 | 0 |
| rankify | exact | 85 | 14% | 46% | 0 | 15 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.64 | 0.84 | 0.94 | 0.97 | 0.98 |
| **rankify-closest** | 0.34 | 0.62 | 0.82 | 0.95 | 0.98 | 0.98 |
| **rankify-per-round** | 0.34 | 0.64 | 0.84 | 0.94 | 0.97 | 0.98 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 65% | 52% | 17/20 |
| **rankify-closest** | 75% | 70% | 0/20 |
| **rankify-per-round** | 62% | 49% | 20/20 |

## 10 items, careless judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 16 · 0.7 min (20/20) | 28 · 1.2 min (20/20) | 42 · 2.1 min (20/20) |
| **rankify-closest** | 24 · 1.1 min (18/20) | 22 · 1.0 min (17/20) | 40 · 2.0 min (17/20) |
| **rankify-per-round** | 16 · 0.7 min (20/20) | 27 · 1.1 min (20/20) | 46 · 2.2 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 60 | 2.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 83 | 4.6 |
| exact | 20/20 | 20/20 | 100% of pairs right | 140 | 7.6 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 10/20 | 10/10 | #1 right in 10/10 | 62 | 2.9 |
| stable | 3/20 | 3/3 | 100% of pairs right | 96 | 4.7 |
| exact | 1/20 | 1/1 | 100% of pairs right | 141 | 7.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 20/20 | #1 right in 20/20 | 56 | 2.7 |
| stable | 20/20 | 20/20 | 100% of pairs right | 84 | 4.5 |
| exact | 20/20 | 20/20 | 100% of pairs right | 144 | 7.8 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick 62%, stable 113%, exact 106%
- rankify's time as a share of rankify-per-round's (per second against per round): quick 100%, stable 110%, exact 94%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.6 s | 0% | 0% |
| rankify | stable | 100% · 2.9 s | 0% | 0% |
| rankify | exact | 100% · 3.1 s | 0% | 0% |
| rankify-closest | quick | 100% · 3.8 s | 0% | 0% |
| rankify-closest | stable | 100% · 3.9 s | 0% | 0% |
| rankify-closest | exact | 100% · 4.2 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.6 s | 0% | 0% |
| rankify-per-round | stable | 100% · 2.8 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.2 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 74 | 50% | 59% | 0 | 0 |
| rankify | stable | 84 | 44% | 46% | 0 | 0 |
| rankify | exact | 100 | 37% | 52% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.58 | 0.87 | 0.96 | 0.96 | 1.00 |
| **rankify-closest** | 0.64 | 0.87 | 0.98 | 1.00 | 1.00 |
| **rankify-per-round** | 0.58 | 0.87 | 0.96 | 0.96 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 57% | 44% | 20/20 |
| **rankify-closest** | 68% | 63% | 1/20 |
| **rankify-per-round** | 57% | 46% | 20/20 |

## 20 items, careless judge

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 50 · 2.1 min (19/20) | 81 · 3.8 min (20/20) | 178 · 10.1 min (20/20) |
| **rankify-closest** | 64 · 2.6 min (13/20) | — (3/20) | — (9/20) |
| **rankify-per-round** | 42 · 1.7 min (20/20) | 89 · 3.8 min (20/20) | 160 · 9.4 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 80 | 3.8 |
| stable | 20/20 | 20/20 | 100% of pairs right | 172 | 9.3 |
| exact | 16/20 | 16/16 | 100% of pairs right | 369 | 23.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-closest stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 13/20 | 8/13 | #1 right in 13/13 | 78 | 3.3 |
| stable | 4/20 | 2/4 | 100% of pairs right | 158 | 8.5 |
| exact | 2/20 | 1/2 | 95% of pairs right | 398 | 27.0 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-per-round stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 19/20 | #1 right in 20/20 | 72 | 3.5 |
| stable | 20/20 | 20/20 | 100% of pairs right | 178 | 9.8 |
| exact | 20/20 | 17/20 | 99% of pairs right | 366 | 23.7 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-closest's (order information against closest to 50/50): quick 81%, stable n/a, exact n/a
- rankify's time as a share of rankify-per-round's (per second against per round): quick 122%, stable 99%, exact 108%

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 100% · 2.5 s | 0% | 0% |
| rankify | stable | 100% · 3.0 s | 0% | 0% |
| rankify | exact | 100% · 3.6 s | 0% | 0% |
| rankify-closest | quick | 100% · 3.5 s | 0% | 0% |
| rankify-closest | stable | 100% · 4.1 s | 0% | 0% |
| rankify-closest | exact | 100% · 4.3 s | 0% | 0% |
| rankify-per-round | quick | 100% · 2.5 s | 0% | 0% |
| rankify-per-round | stable | 100% · 3.1 s | 0% | 0% |
| rankify-per-round | exact | 100% · 3.7 s | 0% | 0% |

Rounds left (G7: the range holds the actual rounds left 70–90% of the time, the median is off by at most 25%). Forecasts made at rounds 0, 10, 25, 50, 100. Lists that ran out of budget add their known misses; their other forecasts can't be scored and are counted as "Unscored".

| Method | Mode | Scored | Range held | Median off by (median) | "At least" | Unscored |
|---|---|---|---|---|---|---|
| rankify | quick | 81 | 69% | 33% | 0 | 0 |
| rankify | stable | 100 | 68% | 24% | 0 | 0 |
| rankify | exact | 80 | 8% | 47% | 0 | 20 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.34 | 0.61 | 0.82 | 0.92 | 0.97 | 0.99 |
| **rankify-closest** | 0.34 | 0.60 | 0.81 | 0.94 | 0.97 | 0.98 |
| **rankify-per-round** | 0.34 | 0.62 | 0.83 | 0.93 | 0.96 | 0.99 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 70% | 54% | 16/20 |
| **rankify-closest** | 80% | 73% | 2/20 |
| **rankify-per-round** | 65% | 50% | 20/20 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 10 | human | 0.043 | 98% |
| **rankify** | 10 | normal | 0.020 | 98% |
| **rankify** | 10 | careless | 0.026 | 99% |
| **rankify** | 20 | human | 0.048 | 88% |
| **rankify** | 20 | normal | 0.037 | 100% |
| **rankify** | 20 | careless | 0.051 | 99% |
| **rankify-closest** | 10 | human | 0.066 | 99% |
| **rankify-closest** | 10 | normal | 0.134 | 100% |
| **rankify-closest** | 10 | careless | 0.104 | 99% |
| **rankify-closest** | 20 | human | 0.027 | 89% |
| **rankify-closest** | 20 | normal | 0.131 | 100% |
| **rankify-closest** | 20 | careless | 0.145 | 100% |
| **rankify-per-round** | 10 | human | 0.048 | 98% |
| **rankify-per-round** | 10 | normal | 0.031 | 98% |
| **rankify-per-round** | 10 | careless | 0.045 | 100% |
| **rankify-per-round** | 20 | human | 0.030 | 93% |
| **rankify-per-round** | 20 | normal | 0.035 | 100% |
| **rankify-per-round** | 20 | careless | 0.032 | 100% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/120 lists; median τ between the two rankings 1.00
- rankify-closest: #1 changed in 0/120 lists; median τ between the two rankings 1.00
- rankify-per-round: #1 changed in 0/120 lists; median τ between the two rankings 1.00

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 3.5 | 3.9 | 1.5 |
| **rankify-closest** | 3.7 | 4.1 | 1.5 |
| **rankify-per-round** | 3.5 | 3.9 | 1.5 |

A real `rankify` subprocess (20 items, includes Python start-up): next 922 ms, answer 77 ms, show 74 ms.

## What each method offers

| Feature | rankify | rankify-closest | rankify-per-round |
|---|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | yes: the relevant pair closest to 50/50 | yes: order information per round |
| Knows when it is done | yes: confidence target, or nothing worth asking | yes: confidence target, or nothing worth asking | yes: confidence target, or nothing worth asking |
| Rounds left | yes: simulated, with a 10–90% range | yes: simulated, with a 10–90% range | yes: simulated, with a 10–90% range |
| Precision modes | yes: quick, stable, exact | yes: quick, stable, exact | yes: quick, stable, exact |
| Pick / rank rounds | no; `new --rounds mixed` adds them | no; `new --rounds mixed` adds them | no; `new --rounds mixed` adds them |
| Confidence and Could be | yes | yes | yes |
| Same answers, any order, same ranking | yes | yes | yes |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
- How long a person takes to pick from or rank 3 to 5 items is a guess in both the judge and the planner. The planner switches to the judge's own times after 8 answers of a kind and size.
