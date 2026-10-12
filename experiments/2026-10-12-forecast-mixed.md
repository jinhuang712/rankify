# Benchmark: rankify against rating systems for human judges

> **Reused runs.** The 640 runs of the rating systems and the sorts came from the Phase 4 benchmark (which reused them from Phase 3): their code didn't change. Both rankify variants ran again, to record the new rounds-left forecasts. Apart from the forecasts and timings, all 240 pairs runs match Phase 4 exactly. 18 of 240 mixed runs differ: the planner now computes the information of an ordering in a faster way that agrees to 1e-15, which changes which of two equally good sets is asked. The mixed results moved only slightly (G3 time shares 100%, 63%, 74% against 100%, 62%, 76%).

> **Exact with a larger budget.** With 20 rounds per item, Exact sessions on pairs don't finish, so their forecasts can't be scored here. A separate run gave Exact 60 rounds per item (human judge, 20 lists): every session finished. Pairs: the range held 71% (10 items) and 65% (20 items), the median off by 11% and 5%. Mixed: 68% and 55%, off by 30% and 21%.

- Date: 2026-10-12 06:20 UTC
- Code: commit 3e97d4b + uncommitted changes, engine 0.3.0
- Setup: 10, 20 items; judges: human, perfect; 20 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 1061 s for 480 runs; the other 640 came from the cache.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify as shipped (pairs); rankify-mixed (the same with `new --rounds mixed`, which also asks picks and rankings of 3 to 5 items); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and two sorts as reference lines only. The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 75% | 4% | 3.1 |
| perfect | 100% | 0% | 3.0 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 39 · 1.8 min (16/20) | 73 · 3.3 min (14/20) | — (10/20) |
| **rankify-mixed** | 12 · 1.3 min (18/20) | 36 · 4.0 min (14/20) | — (10/20) |
| elo | 64 · 2.8 min (17/20) | 118 · 5.0 min (13/20) | — (2/20) |
| elo-close | 96 · 4.9 min (20/20) | 118 · 5.4 min (14/20) | — (2/20) |
| glicko2 | 70 · 3.1 min (17/20) | 131 · 5.4 min (14/20) | — (5/20) |
| trueskill | 78 · 3.1 min (17/20) | 112 · 4.6 min (15/20) | — (8/20) |
| openskill | 70 · 3.1 min (17/20) | 120 · 4.9 min (13/20) | — (4/20) |
| arena | 70 · 3.0 min (17/20) | 132 · 5.4 min (13/20) | — (3/20) |
| just-sort-it (reference) | 54 · 2.4 min (18/20) | 80 · 3.5 min (16/20) | — (7/20) |
| insertion-sort (reference) | — (6/20) | — (5/20) | — (0/20) |

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
| rankify | quick | 84 | 69% | 20% | 0 | 0 |
| rankify | stable | 94 | 73% | 16% | 0 | 0 |
| rankify | exact | 45 | 47% | 24% | 0 | 55 |
| rankify-mixed | quick | 57 | 74% | 36% | 0 | 0 |
| rankify-mixed | stable | 66 | 83% | 18% | 0 | 0 |
| rankify-mixed | exact | 79 | 68% | 31% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.49 | 0.80 | 0.82 | 0.89 | 0.91 |
| **rankify-mixed** | 0.80 | 0.87 | 0.91 | 0.96 | 0.96 |
| elo | 0.49 | 0.60 | 0.78 | 0.82 | 0.84 |
| elo-close | 0.53 | 0.64 | 0.78 | 0.78 | 0.82 |
| glicko2 | 0.49 | 0.62 | 0.73 | 0.84 | 0.87 |
| trueskill | 0.51 | 0.64 | 0.73 | 0.82 | 0.87 |
| openskill | 0.51 | 0.64 | 0.76 | 0.87 | 0.87 |
| arena | 0.47 | 0.62 | 0.76 | 0.84 | 0.89 |
| just-sort-it (reference) | 0.44 | 0.69 | 0.80 | 0.87 | 0.91 |
| insertion-sort (reference) | 0.16 | 0.71 | 0.71 | 0.71 | 0.71 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 86% | 78% | 9/20 |
| **rankify-mixed** | 87% | 57% | 20/20 |
| elo | 91% | 77% | 0/20 |
| elo-close | 90% | 81% | 0/20 |
| glicko2 | 90% | 76% | 0/20 |
| trueskill | 90% | 75% | 0/20 |
| openskill | 90% | 76% | 0/20 |
| arena | 90% | 76% | 0/20 |
| just-sort-it (reference) | 86% | 74% | 0/20 |
| insertion-sort (reference) | 0% | 0% | 20/20 |

## 20 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 74 · 3.4 min (12/20) | — (5/20) | — (0/20) |
| **rankify-mixed** | 28 · 3.6 min (13/20) | — (3/20) | — (0/20) |
| elo | 315 · 13.3 min (12/20) | — (4/20) | — (0/20) |
| elo-close | 184 · 8.6 min (17/20) | — (3/20) | — (0/20) |
| glicko2 | 126 · 5.6 min (15/20) | — (2/20) | — (0/20) |
| trueskill | 176 · 7.3 min (14/20) | — (4/20) | — (0/20) |
| openskill | 227 · 10.1 min (13/20) | — (6/20) | — (0/20) |
| arena | 290 · 12.1 min (14/20) | — (5/20) | — (0/20) |
| just-sort-it (reference) | 141 · 6.0 min (15/20) | — (5/20) | — (0/20) |
| insertion-sort (reference) | — (3/20) | — (0/20) | — (0/20) |

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
| rankify-mixed | quick | 61 | 80% | 29% | 0 | 0 |
| rankify-mixed | stable | 81 | 79% | 20% | 0 | 0 |
| rankify-mixed | exact | 100 | 55% | 24% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.26 | 0.54 | 0.68 | 0.79 | 0.83 | 0.86 |
| **rankify-mixed** | 0.57 | 0.74 | 0.83 | 0.87 | 0.89 | 0.89 |
| elo | 0.33 | 0.49 | 0.63 | 0.69 | 0.73 | 0.79 |
| elo-close | 0.35 | 0.48 | 0.62 | 0.69 | 0.73 | 0.79 |
| glicko2 | 0.33 | 0.52 | 0.63 | 0.71 | 0.76 | 0.81 |
| trueskill | 0.32 | 0.52 | 0.62 | 0.71 | 0.77 | 0.83 |
| openskill | 0.32 | 0.51 | 0.63 | 0.72 | 0.76 | 0.79 |
| arena | 0.34 | 0.51 | 0.60 | 0.73 | 0.78 | 0.82 |
| just-sort-it (reference) | 0.29 | 0.44 | 0.61 | 0.71 | 0.77 | 0.83 |
| insertion-sort (reference) | 0.02 | 0.14 | 0.45 | 0.67 | 0.67 | 0.67 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 87% | 73% | 0/20 |
| **rankify-mixed** | 90% | 35% | 20/20 |
| elo | 90% | 58% | 0/20 |
| elo-close | 88% | 69% | 0/20 |
| glicko2 | 90% | 58% | 0/20 |
| trueskill | 90% | 58% | 0/20 |
| openskill | 90% | 58% | 0/20 |
| arena | 90% | 58% | 0/20 |
| just-sort-it (reference) | 84% | 57% | 0/20 |
| insertion-sort (reference) | 0% | 0% | 20/20 |

## 10 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 15 · 0.7 min (20/20) | 16 · 0.7 min (20/20) | 29 · 1.3 min (20/20) |
| **rankify-mixed** | 6 · 0.6 min (20/20) | 6 · 0.9 min (20/20) | 8 · 1.0 min (20/20) |
| elo | 46 · 2.0 min (19/20) | 74 · 3.2 min (19/20) | 156 · 6.8 min (12/20) |
| elo-close | 30 · 1.5 min (20/20) | 46 · 2.2 min (20/20) | 120 · 5.9 min (16/20) |
| glicko2 | 44 · 1.8 min (20/20) | 52 · 2.1 min (19/20) | 92 · 3.6 min (19/20) |
| trueskill | 44 · 1.8 min (20/20) | 50 · 2.1 min (19/20) | 91 · 3.6 min (19/20) |
| openskill | 44 · 1.8 min (20/20) | 62 · 2.4 min (20/20) | 104 · 4.4 min (16/20) |
| arena | 41 · 1.7 min (20/20) | 50 · 2.2 min (20/20) | 84 · 3.5 min (20/20) |
| just-sort-it (reference) | 26 · 1.1 min (20/20) | 30 · 1.3 min (20/20) | 36 · 1.6 min (20/20) |
| insertion-sort (reference) | 20 · 0.9 min (20/20) | 22 · 1.0 min (20/20) | 22 · 1.0 min (20/20) |

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
| rankify | stable | 80 | 26% | 98% | 0 | 0 |
| rankify | exact | 80 | 21% | 164% | 0 | 0 |
| rankify-mixed | quick | 40 | 28% | 200% | 0 | 0 |
| rankify-mixed | stable | 50 | 24% | 112% | 0 | 0 |
| rankify-mixed | exact | 60 | 28% | 171% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.60 | 0.96 | 1.00 | 1.00 | 1.00 |
| **rankify-mixed** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| elo | 0.47 | 0.71 | 0.84 | 0.91 | 0.96 |
| elo-close | 0.62 | 0.82 | 0.91 | 0.91 | 1.00 |
| glicko2 | 0.49 | 0.78 | 0.89 | 1.00 | 1.00 |
| trueskill | 0.47 | 0.80 | 0.91 | 1.00 | 1.00 |
| openskill | 0.47 | 0.76 | 0.87 | 0.96 | 1.00 |
| arena | 0.56 | 0.78 | 0.96 | 1.00 | 1.00 |
| just-sort-it (reference) | 0.56 | 0.87 | 1.00 | 1.00 | 1.00 |
| insertion-sort (reference) | 0.29 | 1.00 | 1.00 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 17% | 5% | 20/20 |
| **rankify-mixed** | 9% | 0% | 20/20 |
| elo | 83% | 72% | 0/20 |
| elo-close | 81% | 75% | 0/20 |
| glicko2 | 74% | 60% | 0/20 |
| trueskill | 74% | 60% | 0/20 |
| openskill | 80% | 67% | 0/20 |
| arena | 72% | 58% | 0/20 |
| just-sort-it (reference) | 28% | 15% | 0/20 |
| insertion-sort (reference) | 0% | 0% | 20/20 |

## 20 items, perfect judge (sanity check)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 34 · 1.6 min (20/20) | 72 · 3.2 min (20/20) | 81 · 4.1 min (20/20) |
| **rankify-mixed** | 13 · 1.6 min (20/20) | 14 · 2.0 min (20/20) | 22 · 3.0 min (20/20) |
| elo | 191 · 8.4 min (18/20) | 374 · 16.2 min (11/20) | — (0/20) |
| elo-close | 73 · 3.5 min (20/20) | 174 · 9.1 min (20/20) | — (0/20) |
| glicko2 | 89 · 4.0 min (19/20) | 270 · 11.6 min (15/20) | — (3/20) |
| trueskill | 84 · 3.8 min (19/20) | 269 · 11.4 min (14/20) | — (2/20) |
| openskill | 132 · 5.7 min (19/20) | 301 · 13.3 min (15/20) | — (2/20) |
| arena | 64 · 2.7 min (19/20) | 208 · 8.6 min (18/20) | — (7/20) |
| just-sort-it (reference) | 98 · 4.7 min (20/20) | 110 · 5.2 min (20/20) | 128 · 6.2 min (20/20) |
| insertion-sort (reference) | 44 · 2.3 min (20/20) | 58 · 3.1 min (20/20) | 62 · 3.3 min (20/20) |

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
| rankify | quick | 80 | 18% | 84% | 0 | 0 |
| rankify | stable | 100 | 13% | 73% | 0 | 0 |
| rankify | exact | 100 | 0% | 121% | 0 | 0 |
| rankify-mixed | quick | 41 | 2% | 140% | 0 | 0 |
| rankify-mixed | stable | 62 | 21% | 126% | 0 | 0 |
| rankify-mixed | exact | 100 | 58% | 51% | 0 | 0 |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.37 | 0.67 | 0.87 | 1.00 | 1.00 | 1.00 |
| **rankify-mixed** | 0.76 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| elo | 0.42 | 0.53 | 0.68 | 0.76 | 0.85 | 0.91 |
| elo-close | 0.39 | 0.61 | 0.76 | 0.87 | 0.89 | 0.94 |
| glicko2 | 0.42 | 0.57 | 0.73 | 0.84 | 0.92 | 0.96 |
| trueskill | 0.43 | 0.57 | 0.72 | 0.84 | 0.92 | 0.96 |
| openskill | 0.42 | 0.54 | 0.68 | 0.81 | 0.88 | 0.95 |
| arena | 0.41 | 0.61 | 0.78 | 0.88 | 0.96 | 0.99 |
| just-sort-it (reference) | 0.27 | 0.36 | 0.72 | 0.94 | 1.00 | 1.00 |
| insertion-sort (reference) | 0.03 | 0.21 | 0.68 | 1.00 | 1.00 | 1.00 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 16% | 5% | 20/20 |
| **rankify-mixed** | 7% | 0% | 20/20 |
| elo | 81% | 58% | 0/20 |
| elo-close | 83% | 75% | 0/20 |
| glicko2 | 81% | 57% | 0/20 |
| trueskill | 81% | 57% | 0/20 |
| openskill | 81% | 58% | 0/20 |
| arena | 80% | 56% | 0/20 |
| just-sort-it (reference) | 39% | 21% | 0/20 |
| insertion-sort (reference) | 0% | 0% | 20/20 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 10 | human | 0.043 | 98% |
| **rankify** | 10 | perfect | 0.038 | 100% |
| **rankify** | 20 | human | 0.048 | 88% |
| **rankify** | 20 | perfect | 0.039 | 100% |
| **rankify-mixed** | 10 | human | 0.047 | 96% |
| **rankify-mixed** | 10 | perfect | 0.038 | 100% |
| **rankify-mixed** | 20 | human | 0.023 | 93% |
| **rankify-mixed** | 20 | perfect | 0.033 | 100% |
| glicko2 | 10 | human | 0.045 | 98% |
| glicko2 | 10 | perfect | 0.151 | 100% |
| glicko2 | 20 | human | 0.030 | 96% |
| glicko2 | 20 | perfect | 0.121 | 100% |
| trueskill | 10 | human | 0.035 | 95% |
| trueskill | 10 | perfect | 0.117 | 100% |
| trueskill | 20 | human | 0.037 | 94% |
| trueskill | 20 | perfect | 0.097 | 100% |
| openskill | 10 | human | 0.042 | 98% |
| openskill | 10 | perfect | 0.156 | 100% |
| openskill | 20 | human | 0.018 | 98% |
| openskill | 20 | perfect | 0.133 | 100% |
| arena | 10 | human | 0.028 | 97% |
| arena | 10 | perfect | 0.090 | 100% |
| arena | 20 | human | 0.023 | 94% |
| arena | 20 | perfect | 0.124 | 100% |
| just-sort-it (reference) | 10 | human | 0.040 | 98% |
| just-sort-it (reference) | 10 | perfect | 0.030 | 100% |
| just-sort-it (reference) | 20 | human | 0.028 | 96% |
| just-sort-it (reference) | 20 | perfect | 0.053 | 100% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/80 lists; median τ between the two rankings 1.00
- rankify-mixed: #1 changed in 0/80 lists; median τ between the two rankings 1.00
- elo: #1 changed in 9/80 lists; median τ between the two rankings 0.95
- glicko2: #1 changed in 1/80 lists; median τ between the two rankings 0.97
- trueskill: #1 changed in 3/80 lists; median τ between the two rankings 0.97
- openskill: #1 changed in 3/80 lists; median τ between the two rankings 0.96

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 3.4 | 3.9 | 1.4 |
| **rankify-mixed** | 5.3 | 4.4 | 1.4 |
| elo | 1.3 | 2.4 | 1.2 |
| elo-close | 2.3 | 2.3 | 1.2 |
| glicko2 | 1.3 | 3.7 | 1.3 |
| trueskill | 1.3 | 8.7 | 1.3 |
| openskill | 1.3 | 4.3 | 1.3 |
| arena | 1.3 | 3.4 | 1.2 |
| just-sort-it (reference) | 2.4 | 4.6 | 1.3 |
| insertion-sort (reference) | 1.4 | 1.5 | 1.2 |

A real `rankify` subprocess (20 items, includes Python start-up): next 913 ms, answer 74 ms, show 70 ms.

## What each method offers

| Feature | rankify | rankify-mixed | elo | elo-close | glicko2 | trueskill | openskill | arena | just-sort-it | insertion-sort |
|---|---|---|---|---|---|---|---|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | yes: order information per second, weighted by the mode | no: random pairs | yes: close ratings | no: random pairs | no: random pairs | no: random pairs | no: random pairs | yes: quicksort | yes: binary search |
| Knows when it is done | yes: confidence target, or nothing worth asking | yes: confidence target, or nothing worth asking | no | no | no | no | no | no | no | yes, but trusts every answer |
| Rounds left | no (Phase 4) | no (Phase 4) | no | no | no | no | no | no | no | no |
| Precision modes | yes: quick, stable, exact | yes: quick, stable, exact | no | no | no | no | no | no | no | no |
| Pick / rank rounds | no; `new --rounds mixed` adds them | yes: picks and rankings of 3 to 5, when they teach more per second | no | no | no | no | no | no | no | no |
| Confidence and Could be | yes | yes | no | no | yes (from RD) | yes (from sigma) | yes (from sigma) | yes (our fit) | yes (our fit) | no |
| Same answers, any order, same ranking | yes | yes | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | yes | yes | n/a |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
- How long a person takes to pick from or rank 3 to 5 items is a guess in both the judge and the planner. The planner switches to the judge's own times after 8 answers of a kind and size.
