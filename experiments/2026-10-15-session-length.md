# Session length: the EP fit and the repeat rules against the shipped defaults

- Date: 2026-10-15
- Code: 773c184 (step 4), engine 0.3.0, switches set per session as step 4 did: `service.EP_FIT` (fit: `laplace` is shipped, `ep` is the new fit) and `planner.ASK_AGAIN` (`always` is shipped, `contradicted`, `once`). Six settings in all. No default was changed.
- Lists: practice lists only (seeds 70000 + 1000 × items + list number, lists 0–19), never the benchmark's test lists. The first 10 lists of each size are step 4's. 10 and 20 items, 20 lists per setting, budget 20 rounds per item, benchmark-shaped hidden scores.
- Judges: perfect, normal, careless, human and noisy, as in the benchmark. Both modes, Quick and Stable, each run in its own session.
- Driven through the service layer with `bench.run_one`; the rounds-left forecast was off, as in step 4.
- With 20 lists per setting, differences of 1–3 lists in accuracy, or about 10% in rounds, can be chance.

## Why

The first real session ended after about 20 answers. Step 4 found two causes that lengthen sessions, the Laplace fit's over-doubt and repeated pairs, and put a fix for each behind a switch. This run asks how many questions each setting needs before the ranking is right, how long it keeps asking after that, and how good the ranking is when a person stops at 20 or 40 answers.

"Reached" is the benchmark's rule: the first round from which the mode's target holds for the next CONFIRM rounds, or to the session's end. "Right at the stop" means the target really holds when rankify stops by itself.

## 1. At 20 answers, list size decides, not the settings

After 20 answers, lists where the Quick target holds (Quick mode, out of 20):

| Judge | 20 items, shipped | 20 items, EP | 10 items, shipped | 10 items, EP |
|---|---|---|---|---|
| perfect | 0 | 2 | 20 | 20 |
| normal | 0 | 0 | 14 | 18 |
| careless | 1 | 1 | 13 | 14 |
| human | 0 | 1 | 5 | 8 |
| noisy | 2 | 1 | 6 | 5 |

- With 20 items, no setting gets the top 3 right after 20 answers in more than 2 of 20 lists, even with a perfect judge. 20 answers barely show each item once; even the best possible tournament needs about 25 comparisons just to find the top 3 of 20.
- The repeat rules make no difference to the first 20 answers on 20 items: in all 400 sessions per fit, the ranking after 10 and after 20 answers was the same under all three rules. rankify asks no repeats that early. On 10 items they start to differ by answer 20.
- With 10 items, EP has the Quick target right after 20 answers more often for the normal judge (14 → 18 of 20) and the human judge (5 → 8). The other judges are within chance.

## 2. The EP fit reaches targets sooner and stops sooner, at the same accuracy for clear judges

Rounds until the target is reached, shipped → EP (median; lists that reached it in brackets when fewer than 20):

| Judge | 20 items, Quick | 20 items, Stable | 10 items, Quick | 10 items, Stable |
|---|---|---|---|---|
| perfect | 44 → 27 | 56 → 44 | 14 → 13 | 16 → 16 |
| normal | 38 → 28 | 70 → 51 | 18 → 15 (19) | 32 (19) → 24 (18) |
| careless | 44 → 38 | 77 (18) → 70 | 18 → 18 | 32 → 30 (19) |
| human | 75 (17) → 64 (16) | — (9) → — (10) | 48 (14) → 32 (19) | 52 (17) → 48 (15) |
| noisy | 67 (17) → 52 (14) | 166 (11) → 188 (12) | 24 (16) → 31 (16) | 46 (18) → 66 (15) |

Rounds at rankify's own stop, shipped → EP (median), and lists right at the stop:

| Judge | 20 items, Quick | 20 items, Stable | 10 items, Quick | 10 items, Stable |
|---|---|---|---|---|
| perfect | 58 → 44 · 20 → 20 | 103 → 80 · 19 → 20 | 39 → 27 · 20 → 20 | 62 → 40 · 20 → 20 |
| normal | 71 → 49 · 20 → 20 | 134 → 116 · 20 → 18 | 47 → 31 · 20 → 19 | 73 → 54 · 19 → 18 |
| careless | 80 → 62 · 20 → 20 | 143 → 161 · 18 → 19 | 56 → 40 · 20 → 20 | 77 → 74 · 20 → 19 |
| human | 112 → 112 · 16 → 13 | 196 → 210 · 7 → 6 | 84 → 87 · 13 → 16 | 120 → 98 · 14 → 13 |
| noisy | 107 → 93 · 15 → 14 | 184 → 202 · 4 → 9 | 75 → 71 · 15 → 16 | 104 → 112 · 15 → 15 |

- Quick: EP stops 22–34% sooner for the perfect, normal and careless judges at both sizes, with the same accuracy. For the human and noisy judges the stop moves little (−13% to +4%) and accuracy is within chance.
- Stable: EP stops sooner for the perfect and normal judges (13–35%), but later for the careless, human and noisy judges on 20 items (+7% to +13%), as step 4 found on 10 lists. On 10 items it is sooner or about the same, except noisy (+8%).
- Reaching the target: EP gets there sooner in 14 of the 20 cells and in the same number of rounds in 2. It is slower in 3, all for the noisy judge. For the human judge in 20-item Stable, neither fit reaches it in most lists.

## 3. The repeat rules shorten the tail, and lose accuracy for judges who slip

Rounds at the stop · lists right at the stop, with EP, by repeat rule (`always` → `contradicted` / `once`):

| Judge | 20 items, Quick | 20 items, Stable | 10 items, Quick | 10 items, Stable |
|---|---|---|---|---|
| perfect | 44 · 20 → 47 · 20 / 44 · 20 | 80 · 20 → 73 · 20 / 78 · 20 | 27 · 20 → 28 · 20 / 29 · 20 | 40 · 20 → 35 · 20 / 38 · 20 |
| normal | 49 · 20 → 48 · 17 / 54 · 19 | 116 · 18 → 77 · 15 / 87 · 15 | 31 · 19 → 28 · 18 / 32 · 18 | 54 · 18 → 34 · 17 / 40 · 17 |
| careless | 62 · 20 → 50 · 14 / 59 · 16 | 161 · 19 → 96 · 10 / 96 · 9 | 40 · 20 → 29 · 14 / 36 · 16 | 74 · 19 → 36 · 15 / 44 · 15 |
| human | 112 · 13 → 64 · 11 / 68 · 11 | 210 · 6 → 106 · 0 / 122 · 1 | 87 · 16 → 32 · 10 / 36 · 8 | 98 · 13 → 40 · 7 / 50 · 7 |
| noisy | 93 · 14 → 54 · 8 / 61 · 11 | 202 · 9 → 103 · 3 / 117 · 1 | 71 · 16 → 32 · 10 / 38 · 14 | 112 · 15 → 38 · 4 / 48 · 7 |

- Either rule cuts the session by a fifth to two thirds for the careless, human and noisy judges, and by up to 37% for the normal judge.
- For the perfect judge they change little: EP alone already removes most of the tail.
- For every judge who slips, fewer lists are right at the stop: summed over the four cells, careless 78 → 53 (contradicted) and 56 (once), human 48 → 28 and 27, noisy 54 → 25 and 33. This repeats step 4's finding on twice the lists and on 10 items. The Laplace fit with either rule loses about as much (see the logs).
- They don't change the first 20 answers on 20 items (section 1), so they can't help a person who stops there.

## Conclusions

- **The 20-answer stop is mostly about list size.** With 20 items, no setting can give a right top 3 after 20 answers. With 10 items, the shipped settings already get it in most lists for clear judges, and EP gets it in more.
- **EP is a clear win for Quick and for clear judges.** It reaches the target and stops sooner, at the same accuracy. In Stable mode it is slower to stop for judges who slip on 20 items.
- **Neither repeat rule is ready.** Both shorten the tail, but they cost accuracy at the stop for every judge who makes mistakes, and they don't touch the first 20 answers.

## Proposed defaults (not changed in this commit)

1. **Flip `service.EP_FIT` to `True`.** Quick sessions get 22–34% shorter for clear judges with no accuracy cost, and the targets are reached sooner in most cells. What it costs: slower stops in Stable for judges who slip (+7% to +13% on 20 items), and about 40 ms per answer against 4 ms (step 4; 200 items not measured).
2. **Keep `planner.ASK_AGAIN = "always"`.** The accuracy loss is too large for judges who slip, which real people are. Step 4's next candidate, re-checking only the pairs that decide the mode's target, is still the one to try.
3. **For the 20-answer problem itself,** what remains to test: smaller lists or a first pass on fewer items, rounds that carry more per answer (pick and rank rounds, `rankify-mixed`), and showing a good-enough ranking with honest doubt when the person stops early. None of these was measured here.

## How it was run

Scripts and their output are in [2026-10-15-session-length/](2026-10-15-session-length/):

```sh
uv run python experiments/2026-10-15-session-length/length_eval.py . laplace-always,laplace-contradicted,laplace-once,ep-always,ep-contradicted,ep-once perfect,normal,careless,human,noisy 20 quick,stable 20 4 > n20.jsonl
uv run python experiments/2026-10-15-session-length/summarize.py n20.jsonl > n20.log
```

The same with `10` items gives `n10.log`. `length_eval.py` prints one JSON line per session. The raw lines (1,200 sessions per size) aren't kept: the seeds are fixed, so the command above reproduces them. `summarize.py` turns them into the tables in the logs, which also show the Laplace fit with each repeat rule and the rankings after 40 answers. The sessions ran in a 4-core Linux container, under an hour for 20 items.
