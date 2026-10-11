# Benchmark: rankify against Elo and other methods

- Date: 2026-10-11 15:13 UTC
- Code: commit 1d3cf69 + uncommitted changes, engine 0.1.0
- Setup: 10, 20 items; judges: perfect, noisy; 20 runs per method and setting, with the same hidden orders for every method; budget 20 rounds per item.
- Every method ran through the CLI: `new --method`, then `next`, `answer` and `show` each round.
- A target counts as reached at the first round from which it holds for 10 more rounds, or until the method stops asking. Human time assumes 3 s per pair.
- Wall time: 65 s.

Targets: **Quick** = true #1 at #1 and the true top 3 in the top 3. **Stable** = the top quarter (at least 3) in exactly the right order, every other item within one tier of its true tier. **Exact** = the whole order right.

## 10 items, perfect judge (always right)

Rounds to reach each target (median over runs; `—` = not reached in most runs within the budget; reached/runs in brackets):

| Method | Quick | Stable | Exact | Exact, human time |
|---|---|---|---|---|
| rankify | 41 (19/20) | 44 (19/20) | 96 (18/20) | 4.8 min |
| elo | 58 (19/20) | 69 (18/20) | 186 (12/20) | 9.3 min |
| elo-close | 44 (20/20) | 52 (20/20) | 160 (13/20) | 8.0 min |
| just-sort-it | 24 (20/20) | 25 (20/20) | 47 (20/20) | 2.4 min |
| insertion-sort | 18 (20/20) | 22 (20/20) | 22 (20/20) | 1.1 min |

Kendall τ with the hidden order (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| rankify | 0.56 | 0.78 | 0.96 | 0.96 | 1.00 |
| elo | 0.53 | 0.69 | 0.82 | 0.91 | 1.00 |
| elo-close | 0.58 | 0.78 | 0.87 | 0.96 | 0.96 |
| just-sort-it | 0.53 | 0.87 | 1.00 | 1.00 | 1.00 |
| insertion-sort | 0.42 | 1.00 | 1.00 | 1.00 | 1.00 |

Wasted questions, counted up to the round where Exact was reached (or the whole budget if never). Implied = the answer already followed from earlier answers; with a perfect judge such a round teaches nothing.

| Method | Implied by earlier answers | Exact repeats | Stopped by itself |
|---|---|---|---|
| rankify | 78% | 63% | 0/20 |
| elo | 86% | 75% | 0/20 |
| elo-close | 85% | 80% | 0/20 |
| just-sort-it | 48% | 31% | 0/20 |
| insertion-sort | 0% | 0% | 20/20 |

## 10 items, noisy judge (tells neighbours apart 75% of the time, far items more often)

Rounds to reach each target (median over runs; `—` = not reached in most runs within the budget; reached/runs in brackets):

| Method | Quick | Stable | Exact | Exact, human time |
|---|---|---|---|---|
| rankify | 82 (16/20) | 114 (15/20) | 165 (12/20) | 8.2 min |
| elo | 90 (18/20) | 130 (18/20) | — (9/20) | — |
| elo-close | 64 (20/20) | 74 (19/20) | — (3/20) | — |
| just-sort-it | 49 (19/20) | 74 (19/20) | 134 (14/20) | 6.7 min |
| insertion-sort | — (10/20) | — (8/20) | — (1/20) | — |

Kendall τ with the hidden order (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds |
|---|---|---|---|---|---|
| rankify | 0.53 | 0.73 | 0.82 | 0.91 | 0.96 |
| elo | 0.49 | 0.64 | 0.78 | 0.91 | 0.96 |
| elo-close | 0.56 | 0.76 | 0.87 | 0.91 | 0.96 |
| just-sort-it | 0.47 | 0.78 | 0.91 | 0.96 | 1.00 |
| insertion-sort | 0.36 | 0.87 | 0.87 | 0.87 | 0.87 |

Wasted questions, counted up to the round where Exact was reached (or the whole budget if never). Implied = the answer already followed from earlier answers; with a perfect judge such a round teaches nothing.

| Method | Implied by earlier answers | Exact repeats | Stopped by itself |
|---|---|---|---|
| rankify | 87% | 72% | 0/20 |
| elo | 88% | 75% | 0/20 |
| elo-close | 90% | 83% | 0/20 |
| just-sort-it | 82% | 69% | 0/20 |
| insertion-sort | 0% | 0% | 20/20 |

## 20 items, perfect judge (always right)

Rounds to reach each target (median over runs; `—` = not reached in most runs within the budget; reached/runs in brackets):

| Method | Quick | Stable | Exact | Exact, human time |
|---|---|---|---|---|
| rankify | 174 (19/20) | 302 (15/20) | — (1/20) | — |
| elo | 286 (13/20) | — (8/20) | — (0/20) | — |
| elo-close | 67 (20/20) | 234 (19/20) | — (0/20) | — |
| just-sort-it | 50 (20/20) | 161 (20/20) | 268 (18/20) | 13.4 min |
| insertion-sort | 50 (20/20) | 60 (20/20) | 63 (20/20) | 3.1 min |

Kendall τ with the hidden order (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| rankify | 0.38 | 0.55 | 0.73 | 0.84 | 0.94 | 0.98 |
| elo | 0.37 | 0.53 | 0.66 | 0.74 | 0.86 | 0.93 |
| elo-close | 0.37 | 0.59 | 0.76 | 0.87 | 0.91 | 0.95 |
| just-sort-it | 0.37 | 0.58 | 0.74 | 0.87 | 0.97 | 1.00 |
| insertion-sort | 0.06 | 0.24 | 0.71 | 1.00 | 1.00 | 1.00 |

Wasted questions, counted up to the round where Exact was reached (or the whole budget if never). Implied = the answer already followed from earlier answers; with a perfect judge such a round teaches nothing.

| Method | Implied by earlier answers | Exact repeats | Stopped by itself |
|---|---|---|---|
| rankify | 82% | 58% | 0/20 |
| elo | 82% | 58% | 0/20 |
| elo-close | 84% | 75% | 0/20 |
| just-sort-it | 74% | 51% | 0/20 |
| insertion-sort | 0% | 0% | 20/20 |

## 20 items, noisy judge (tells neighbours apart 75% of the time, far items more often)

Rounds to reach each target (median over runs; `—` = not reached in most runs within the budget; reached/runs in brackets):

| Method | Quick | Stable | Exact | Exact, human time |
|---|---|---|---|---|
| rankify | 191 (16/20) | 268 (13/20) | — (1/20) | — |
| elo | 279 (13/20) | — (7/20) | — (0/20) | — |
| elo-close | 120 (20/20) | 284 (19/20) | — (0/20) | — |
| just-sort-it | 71 (20/20) | 310 (14/20) | — (3/20) | — |
| insertion-sort | 62 (11/20) | — (3/20) | — (0/20) | — |

Kendall τ with the hidden order (median; 1 = identical):

| Method | 10 rounds | 25 rounds | 50 rounds | 100 rounds | 200 rounds | 400 rounds |
|---|---|---|---|---|---|---|
| rankify | 0.38 | 0.55 | 0.73 | 0.81 | 0.91 | 0.95 |
| elo | 0.37 | 0.52 | 0.67 | 0.75 | 0.86 | 0.93 |
| elo-close | 0.37 | 0.58 | 0.74 | 0.83 | 0.88 | 0.93 |
| just-sort-it | 0.32 | 0.62 | 0.76 | 0.88 | 0.95 | 0.99 |
| insertion-sort | 0.05 | 0.23 | 0.62 | 0.94 | 0.94 | 0.94 |

Wasted questions, counted up to the round where Exact was reached (or the whole budget if never). Implied = the answer already followed from earlier answers; with a perfect judge such a round teaches nothing.

| Method | Implied by earlier answers | Exact repeats | Stopped by itself |
|---|---|---|---|
| rankify | 84% | 58% | 0/20 |
| elo | 84% | 58% | 0/20 |
| elo-close | 86% | 74% | 0/20 |
| just-sort-it | 83% | 60% | 0/20 |
| insertion-sort | 0% | 0% | 20/20 |

## Confidence (methods that report it)

Measured on the final ranking of each run. Calibration error: how far stated Confidence is from the share of neighbour pairs actually in the right order (goal G5: ≤ 0.05). Could be coverage: share of items whose true rank is inside the 90% range (goal G6: 85–95%).

| Method | Items | Judge | Calibration error | Could be coverage |
|---|---|---|---|---|
| just-sort-it | 10 | noisy | 0.088 | 100% |
| rankify | 10 | noisy | 0.074 | 100% |
| just-sort-it | 10 | perfect | 0.043 | 100% |
| rankify | 10 | perfect | 0.109 | 100% |
| just-sort-it | 20 | noisy | 0.150 | 100% |
| rankify | 20 | noisy | 0.114 | 100% |
| just-sort-it | 20 | perfect | 0.176 | 100% |
| rankify | 20 | perfect | 0.145 | 100% |

## Same answers, different order

Each run's answers replayed in two shuffled orders through the method's scoring:

- rankify: #1 changed in 0/80 runs; median τ between the two rankings 1.00
- elo: #1 changed in 2/80 runs; median τ between the two rankings 0.96

## Cost per round

Median milliseconds per CLI call, in-process (real CLI code, no process start-up):

| Method | next | answer | show |
|---|---|---|---|
| rankify | 1.9 | 5.7 | 1.9 |
| elo | 1.9 | 4.1 | 1.8 |
| elo-close | 3.9 | 3.6 | 1.8 |
| just-sort-it | 3.8 | 5.3 | 1.9 |
| insertion-sort | 2.1 | 2.3 | 1.8 |

A real `rankify` subprocess (20 items, includes Python start-up): next 77 ms, answer 79 ms, show 70 ms.

## What each method offers

| Feature | rankify | elo | elo-close | just-sort-it | insertion-sort |
|---|---|---|---|---|---|
| Pair rounds | yes | yes | yes | yes | yes |
| Pick / rank rounds | no (Phase 3) | no | no | no | no |
| Chooses informative pairs | no: random pairs (planner is Phase 2) | no: random pairs | yes: closest ratings | yes: quicksort | yes: binary search |
| Knows when it is done | no (stopping rules are Phase 2) | no | no | no | yes, but trusts every answer |
| Rounds left | no (forecast is Phase 4) | no | no | no | no |
| Precision modes | no (stored, not used until Phase 2) | no | no | no | no |
| Confidence and Could be | yes | no | no | yes (our fit) | no |

## Caveats

- Simulated judges, not people. The noisy judge follows a Bradley–Terry curve, the model rankify and Just Sort It fit, which favours them.
- Elo uses K = 32 and starts every item at 1500. Neither was tuned.
- Human time counts answering only, at a guessed 3 s per pair.
