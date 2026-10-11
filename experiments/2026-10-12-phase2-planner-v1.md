# Benchmark: rankify against rating systems for human judges

- Date: 2026-10-11 17:54 UTC
- Code: commit f82ec51 + uncommitted changes, engine 0.2.0
- Setup: 10, 20 items; judges: human, perfect; 20 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 846 s.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify; rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and two sorts as reference lines only. The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes.

| Judge | Answers right | Can't decide | Seconds per answer |
|---|---|---|---|
| human | 78% | 3% | 2.7 |
| perfect | 100% | 0% | 2.8 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 34 · 1.6 min (12/20) | — (8/20) | — (5/20) |
| elo | 64 · 2.8 min (17/20) | 118 · 5.0 min (13/20) | — (2/20) |
| elo-close | 96 · 4.9 min (20/20) | 118 · 5.4 min (14/20) | — (2/20) |
| glicko2 | 70 · 3.1 min (17/20) | 131 · 5.4 min (14/20) | — (5/20) |
| trueskill | 78 · 3.1 min (17/20) | 112 · 4.6 min (15/20) | — (8/20) |
| openskill | 70 · 3.1 min (17/20) | 120 · 4.9 min (13/20) | — (4/20) |
| arena | 70 · 3.0 min (17/20) | 132 · 5.4 min (13/20) | — (3/20) |
| just-sort-it (reference) | 54 · 2.4 min (18/20) | 80 · 3.5 min (16/20) | — (7/20) |
| insertion-sort (reference) | — (6/20) | — (5/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | Rounds | Minutes |
|---|---|---|---|---|
| quick | 20/20 | 11/20 | 46 | 2.0 |
| stable | 20/20 | 8/20 | 63 | 2.9 |
| exact | 20/20 | 4/20 | 102 | 5.0 |

- rankify's time as a share of elo's (G1: at most 50%): quick 57%, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 66%, stable n/a, exact n/a

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.51 | 0.73 | 0.82 | 0.87 | 0.87 |
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
| **rankify** | 78% | 65% | 20/20 |
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
| **rankify** | — (5/20) | — (1/20) | — (0/20) |
| elo | 315 · 13.3 min (12/20) | — (4/20) | — (0/20) |
| elo-close | 184 · 8.6 min (17/20) | — (3/20) | — (0/20) |
| glicko2 | 126 · 5.6 min (15/20) | — (2/20) | — (0/20) |
| trueskill | 176 · 7.3 min (14/20) | — (4/20) | — (0/20) |
| openskill | 227 · 10.1 min (13/20) | — (6/20) | — (0/20) |
| arena | 290 · 12.1 min (14/20) | — (5/20) | — (0/20) |
| just-sort-it (reference) | 141 · 6.0 min (15/20) | — (5/20) | — (0/20) |
| insertion-sort (reference) | — (3/20) | — (0/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | Rounds | Minutes |
|---|---|---|---|---|
| quick | 20/20 | 5/20 | 58 | 2.4 |
| stable | 20/20 | 1/20 | 122 | 5.8 |
| exact | 20/20 | 0/20 | 253 | 13.1 |

- rankify's time as a share of elo's (G1: at most 50%): quick n/a, stable n/a, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick n/a, stable n/a, exact n/a

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.26 | 0.46 | 0.66 | 0.76 | 0.81 | 0.84 |
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
| **rankify** | 78% | 56% | 20/20 |
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
| **rankify** | 14 · 0.6 min (20/20) | 32 · 1.4 min (20/20) | 26 · 1.1 min (20/20) |
| elo | 46 · 2.0 min (19/20) | 74 · 3.2 min (19/20) | 156 · 6.8 min (12/20) |
| elo-close | 30 · 1.5 min (20/20) | 46 · 2.2 min (20/20) | 120 · 5.9 min (16/20) |
| glicko2 | 44 · 1.8 min (20/20) | 52 · 2.1 min (19/20) | 92 · 3.6 min (19/20) |
| trueskill | 44 · 1.8 min (20/20) | 50 · 2.1 min (19/20) | 91 · 3.6 min (19/20) |
| openskill | 44 · 1.8 min (20/20) | 62 · 2.4 min (20/20) | 104 · 4.4 min (16/20) |
| arena | 41 · 1.7 min (20/20) | 50 · 2.2 min (20/20) | 84 · 3.5 min (20/20) |
| just-sort-it (reference) | 26 · 1.1 min (20/20) | 30 · 1.3 min (20/20) | 36 · 1.6 min (20/20) |
| insertion-sort (reference) | 20 · 0.9 min (20/20) | 22 · 1.0 min (20/20) | 22 · 1.0 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | Rounds | Minutes |
|---|---|---|---|---|
| quick | 20/20 | 20/20 | 30 | 1.2 |
| stable | 20/20 | 20/20 | 67 | 3.1 |
| exact | 20/20 | 20/20 | 84 | 4.2 |

- rankify's time as a share of elo's (G1: at most 50%): quick 27%, stable 43%, exact 17%
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 50%, stable 106%, exact 71%

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.62 | 0.96 | 1.00 | 1.00 | 1.00 |
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
| **rankify** | 15% | 2% | 20/20 |
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
| **rankify** | 29 · 1.2 min (19/20) | 76 · 3.4 min (20/20) | 80 · 3.9 min (20/20) |
| elo | 191 · 8.4 min (18/20) | 374 · 16.2 min (11/20) | — (0/20) |
| elo-close | 73 · 3.5 min (20/20) | 174 · 9.1 min (20/20) | — (0/20) |
| glicko2 | 89 · 4.0 min (19/20) | 270 · 11.6 min (15/20) | — (3/20) |
| trueskill | 84 · 3.8 min (19/20) | 269 · 11.4 min (14/20) | — (2/20) |
| openskill | 132 · 5.7 min (19/20) | 301 · 13.3 min (15/20) | — (2/20) |
| arena | 64 · 2.7 min (19/20) | 208 · 8.6 min (18/20) | — (7/20) |
| just-sort-it (reference) | 98 · 4.7 min (20/20) | 110 · 5.2 min (20/20) | 128 · 6.2 min (20/20) |
| insertion-sort (reference) | 44 · 2.3 min (20/20) | 58 · 3.1 min (20/20) | 62 · 3.3 min (20/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | Rounds | Minutes |
|---|---|---|---|---|
| quick | 20/20 | 19/20 | 58 | 2.3 |
| stable | 20/20 | 20/20 | 135 | 7.0 |
| exact | 20/20 | 20/20 | 248 | 13.8 |

- rankify's time as a share of elo's (G1: at most 50%): quick 14%, stable 21%, exact n/a
- rankify's time as a share of just-sort-it's (G2: at most 80%): quick 26%, stable 65%, exact 63%

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.37 | 0.65 | 0.86 | 1.00 | 1.00 | 1.00 |
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
| **rankify** | 15% | 4% | 20/20 |
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
| **rankify** | 10 | human | 0.037 | 96% |
| **rankify** | 10 | perfect | 0.038 | 100% |
| **rankify** | 20 | human | 0.023 | 96% |
| **rankify** | 20 | perfect | 0.038 | 100% |
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
- elo: #1 changed in 9/80 lists; median τ between the two rankings 0.95
- glicko2: #1 changed in 1/80 lists; median τ between the two rankings 0.97
- trueskill: #1 changed in 3/80 lists; median τ between the two rankings 0.97
- openskill: #1 changed in 3/80 lists; median τ between the two rankings 0.96

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 3.5 | 4.2 | 1.3 |
| elo | 1.3 | 2.5 | 1.2 |
| elo-close | 2.4 | 2.5 | 1.2 |
| glicko2 | 1.3 | 3.9 | 1.3 |
| trueskill | 1.3 | 9.0 | 1.4 |
| openskill | 1.3 | 4.4 | 1.3 |
| arena | 1.3 | 3.7 | 1.3 |
| just-sort-it (reference) | 2.5 | 5.0 | 1.3 |
| insertion-sort (reference) | 1.4 | 1.5 | 1.2 |

A real `rankify` subprocess (20 items, includes Python start-up): next 74 ms, answer 75 ms, show 74 ms.

## What each method offers

| Feature | rankify | elo | elo-close | glicko2 | trueskill | openskill | arena | just-sort-it | insertion-sort |
|---|---|---|---|---|---|---|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | no: random pairs | yes: close ratings | no: random pairs | no: random pairs | no: random pairs | no: random pairs | yes: quicksort | yes: binary search |
| Knows when it is done | yes: confidence target, or nothing worth asking | no | no | no | no | no | no | no | yes, but trusts every answer |
| Rounds left | no (Phase 4) | no | no | no | no | no | no | no | no |
| Precision modes | yes: quick, stable, exact | no | no | no | no | no | no | no | no |
| Pick / rank rounds | no (Phase 3) | no | no | no | no | no | no | no | no |
| Confidence and Could be | yes | no | no | yes (from RD) | yes (from sigma) | yes (from sigma) | yes (our fit) | yes (our fit) | no |
| Same answers, any order, same ranking | yes | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | no: updates one match at a time | yes | yes | n/a |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
