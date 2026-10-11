# Benchmark: rankify against rating systems for human judges

> **Names in this report.** It was generated before the variants were renamed. Here `rankify` is the mixed planner, now `rankify-mixed` (`new --rounds mixed`), and `rankify-pairs` is what ships as `rankify`, asking pairs only. "rankify's time as a share of rankify-pairs's (G3)" is mixed rounds against pairs only.

- Date: 2026-10-11 19:17 UTC
- Code: commit ffcf697 + uncommitted changes, engine 0.3.0
- Setup: 10, 20 items; judges: human; 20 hidden lists per setting, the same for every method; budget 20 rounds per item; wall time 95 s for 120 runs; the other 120 (rankify-pairs, which asks no pick or rank rounds, so its runs don't depend on their time) came from the main Phase 3 benchmark.
- Every method ran through the CLI: `new --method`, then `next`, `answer` (or `--cant-decide`) and `show` each round.
- Hidden scores: a few clear favourites and a crowded middle (Student-t with 3 degrees of freedom, times 1.50).

**Targets.** Quick = the true #1 on top and the true top 3 in the top 3. Stable = the top quarter (at least 3) in the right order, every other item within one tier of its true tier. Exact = the whole order right. Swaps between near-ties (pairs the human judge gets right under 55% of the time) don't count as errors. A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking.

**Methods.** rankify (pairs, picks and rankings); rankify-pairs (the same, asking pairs only); rating systems built for human judges (Elo, Elo with close pairs, Glicko-2, TrueSkill, openskill, and Chatbot-Arena-style Bradley-Terry); and two sorts as reference lines only. The sorts assume a consistent judge, which people are not.

## The judges

**human** (the headline): perceived scores carry noise (Thurstone 1927), noise grows with fatigue, a lean toward the item shown first, occasional random answers (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on close calls (the distance effect; Moyer & Landauer 1967). **perfect**: always right; a sanity check. **noisy**: Bradley-Terry noise only, the model rankify assumes.

A pick or rank round is answered from the same perceived scores, without "can't decide". Its time is a guess: a ranking costs one call per neighbour in the judge's order, a pick one call between the best two plus half an easy call per other item.

| Judge | Pairwise calls right | Can't decide (pairs) | Seconds per round |
|---|---|---|---|
| human | 70% | 7% | 4.7 |

How hard the hidden lists are for the human judge, before lapses and fatigue: 10 items: neighbours told apart 63% of the time (median), 24% of neighbouring pairs are near-ties; 20 items: neighbours told apart 57% of the time (median), 41% of neighbouring pairs are near-ties.

Human judge settings: noise 1.0, fatigue +0.3% per round (up to ×1.6), first-item lean 0.15, lapses 3%, can't-decide up to 30%, 2.0 s per easy answer plus up to 3.0 s on close calls, pick and rank rounds ×2 the guessed time. Source: all guesses until a real session calibrates them.

## 10 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | 12 · 2.9 min (17/20) | 26 · 4.6 min (13/20) | 95 · 12.9 min (11/20) |
| **rankify-pairs** | 39 · 1.8 min (16/20) | 73 · 3.3 min (14/20) | — (10/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 16/20 | #1 right in 19/20 | 38 | 6.1 |
| stable | 20/20 | 11/20 | 86% of pairs right | 50 | 8.6 |
| exact | 20/20 | 6/20 | 88% of pairs right | 98 | 13.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-pairs stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 15/20 | #1 right in 17/20 | 84 | 4.0 |
| stable | 20/20 | 14/20 | 92% of pairs right | 116 | 5.9 |
| exact | 9/20 | 5/9 | 94% of pairs right | 172 | 8.9 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-pairs's (G3: under 100%): quick 158%, stable 139%, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 45% · 3.3 s | 7% · 7.0 s | 48% · 15.0 s |
| rankify | stable | 47% · 3.4 s | 7% · 7.7 s | 46% · 17.0 s |
| rankify | exact | 66% · 3.4 s | 8% · 8.9 s | 26% · 16.4 s |
| rankify-pairs | quick | 100% · 2.6 s | 0% | 0% |
| rankify-pairs | stable | 100% · 2.8 s | 0% | 0% |
| rankify-pairs | exact | 100% · 3.0 s | 0% | 0% |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| **rankify** | 0.80 | 0.87 | 0.91 | 0.93 | 0.96 |
| **rankify-pairs** | 0.49 | 0.80 | 0.82 | 0.89 | 0.91 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 90% | 59% | 20/20 |
| **rankify-pairs** | 86% | 78% | 9/20 |

## 20 items, human judge (the headline)

Rounds and human minutes to reach each target (median over lists; `—` = not reached in most lists within the budget; reached/lists in brackets):

| Method | Quick | Stable | Exact |
|---|---|---|---|
| **rankify** | — (9/20) | — (9/20) | — (0/20) |
| **rankify-pairs** | 74 · 3.4 min (12/20) | — (5/20) | — (0/20) |

When rankify stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 8/20 | #1 right in 19/20 | 38 | 7.7 |
| stable | 20/20 | 9/20 | 91% of pairs right | 89 | 14.5 |
| exact | 20/20 | 0/20 | 74% of pairs right | 330 | 31.2 |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

When rankify-pairs stopped by itself, in each mode (median over lists that stopped):

| Mode | Stopped by itself | Target really met at the stop | G8 at the stop | Rounds | Minutes |
|---|---|---|---|---|---|
| quick | 20/20 | 10/20 | #1 right in 19/20 | 90 | 3.9 |
| stable | 20/20 | 4/20 | 85% of pairs right | 199 | 10.1 |
| exact | 0/20 | 0/0 | — | — | — |

G8 asks less than the targets above: Quick, the true #1 on top in at least 90% of lists; Stable, at least 90% of neighbour pairs in the top quarter in the right order; Exact, at least 95% of all neighbour pairs. Swaps of near-ties don't count.

- rankify's time as a share of rankify-pairs's (G3: under 100%): quick n/a, stable n/a, exact n/a

Round mix, per mode (share of rounds; median seconds per round of that kind):

| Method | Mode | Pairs | Picks | Rankings |
|---|---|---|---|---|
| rankify | quick | 33% · 3.0 s | 8% · 7.6 s | 59% · 15.7 s |
| rankify | stable | 56% · 3.1 s | 14% · 9.3 s | 30% · 16.9 s |
| rankify | exact | 85% · 3.3 s | 6% · 10.1 s | 9% · 17.7 s |
| rankify-pairs | quick | 100% · 2.4 s | 0% | 0% |
| rankify-pairs | stable | 100% · 2.7 s | 0% | 0% |
| rankify-pairs | exact | 100% · 3.1 s | 0% | 0% |

Kendall τ with the hidden scores (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| **rankify** | 0.57 | 0.76 | 0.77 | 0.82 | 0.84 | 0.88 |
| **rankify-pairs** | 0.26 | 0.54 | 0.68 | 0.79 | 0.83 | 0.86 |

Wasted questions, up to the round where Exact was reached (or the whole budget): the answer already followed from earlier answers, or the exact pair was asked before.

| Method | Already implied | Exact repeats | Stopped by itself |
|---|---|---|---|
| **rankify** | 95% | 69% | 20/20 |
| **rankify-pairs** | 87% | 73% | 0/20 |

## Confidence (methods that report it)

Measured on the final ranking of each list. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| **rankify** | 10 | human | 0.027 | 100% |
| **rankify** | 20 | human | 0.043 | 95% |
| **rankify-pairs** | 10 | human | 0.043 | 98% |
| **rankify-pairs** | 20 | human | 0.048 | 88% |

## Same answers, different order

Each list's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/40 lists; median τ between the two rankings 1.00
- rankify-pairs: #1 changed in 0/40 lists; median τ between the two rankings 1.00

## Compute cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| **rankify** | 7.1 | 4.7 | 1.3 |
| **rankify-pairs** | 3.5 | 4.0 | 1.2 |

A real `rankify` subprocess (20 items, includes Python start-up): next 72 ms, answer 72 ms, show 69 ms.

## What each method offers

| Feature | rankify | rankify-pairs |
|---|---|---|
| Chooses informative pairs | yes: order information per second, weighted by the mode | yes: order information per second, weighted by the mode |
| Knows when it is done | yes: confidence target, or nothing worth asking | yes: confidence target, or nothing worth asking |
| Rounds left | no (Phase 4) | no (Phase 4) |
| Precision modes | yes: quick, stable, exact | yes: quick, stable, exact |
| Pick / rank rounds | yes: picks and rankings of 3 to 5, when they teach more per second | no: pairs only, for comparison |
| Confidence and Could be | yes | yes |
| Same answers, any order, same ranking | yes | yes |

## Caveats

- Simulated judges, not people. The human judge's settings are guesses until a real session calibrates them.
- The human judge uses Thurstone (normal-curve) noise, not the Bradley-Terry curve rankify fits, so rankify gets no home advantage from it.
- Rating systems use their default settings (Elo K = 32; Glicko-2 1500 ± 350; TrueSkill and openskill defaults). None was tuned.
- Human time counts answering only.
- How long a person takes to pick from or rank 3 to 5 items is a guess in both the judge and the planner. The planner switches to the judge's own times after 8 answers of a kind and size.
