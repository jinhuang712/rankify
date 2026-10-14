# Step 4: a fit that doubts honestly, and fewer repeated questions

- Date: 2026-10-14
- Code: the step 4 commit that adds this report (on top of c4bdc1e), engine 0.3.0. The new fit (`service.EP_FIT`) and the repeat rules (`planner.ASK_AGAIN`) are switches, both off by default, and each section says how they were set.
- Lists: practice lists only (seeds 70000 + 1000 × items + list number), never the benchmark's test lists. 20 items, 10 lists per setting, budget 20 rounds per item.
- Driven through the service layer, as the benchmark does. The rounds-left forecast was switched off: it never changes which rounds are asked, and it would have doubled the run time.
- Hidden scores: the benchmark's shape (1.5 × Student-t with 3 degrees of freedom: a few clear favourites and a crowded middle) unless a section says otherwise. "Bell curve" means a normal distribution with the same middle crowding (sd 1.70, the same interquartile range).
- Judges: perfect, normal, careless (normal, plus 5% random answers), human and noisy, as in the benchmark.
- With 10 lists per setting, differences under about 10% in rounds, or 1–2 lists in accuracy, can be chance.

## Why

The problem is session length. In the first real session the judge stopped after 20 answers. Three causes came up:

- rankify doubts itself too much with judges who seldom contradict themselves, so it keeps asking after its ranking is already right;
- it asks the same pair again and again;
- its stopping rules were tuned around the first cause.

## 1. rankify doubts itself too much

After the ranking was already right, sessions kept going (median extra rounds):

| Judge | Quick | Stable |
|---|---|---|
| normal | 25 | 76 |
| perfect | 17 | 37 |
| careless | 38 | 70 |

- The rule that held them up was "no item below the settled part can still reach into it". It was the last rule to pass in 6 to 10 of 10 sessions for the clear judges.
- At the Quick stop, rankify gave a 26–29% chance that some item below #3 belonged in the top 3. In fact the top 3 was right in all 30 of those sessions (normal, perfect and careless).
- Could be held the true rank 98–100% of the time for clear judges, against the 92–93% its own draws claim. Whole-number ranks explain only 2–3 points of that.
- The items holding up the stop had been shown 3 to 10 times, so the cause is too much doubt, not unseen items.

**The cause is the fit.** rankify's Laplace fit learns how widely scores spread (the prior width) from the answers. At the Quick stop it learned about 2 for the clear judges (normal 1.94, careless 1.85, perfect 2.05), against a true spread of 9.58 on its own scale. Gaps between items came out squeezed: #1 to #4 at 36–52% of their true size, and the middle of the list (#8 to #13) at 0–11%. The step 3 gap scale widened them by only 1.11–1.13. For the human and noisy judges the width was 1.60 and 1.62 against 2.56, and the #1 to #4 gap came out at 0.86 and 1.12 of its true size.

**The starting belief about the width is not the cause.** Refitting the same answers with a nearly flat starting belief moved the width from 1.94 to 2.05 (normal), from 2.05 to 2.21 (perfect) and from 1.60 to 1.62 (human).

## 2. The new fit: expectation propagation

The Laplace fit centres its bell curve on the single most likely set of scores. "A beats B" fits every larger gap too, so with a judge who seldom contradicts themself most believable scores lie far beyond that peak, and Laplace misses them (Kuss & Rasmussen 2005 found the same in classification). Expectation propagation (EP; Minka 2001) fits each answer's effect so that the posterior's mean and spread along that answer's gap match what the answer really implies. `engine/ep.py` covers pair answers with "can't decide" and the first-slot bonus, and learns the prior width, bonus and tie weight from the answers.

Checks:

- Each answer's moments match brute-force integrals within 2e-7, from narrow to very wide cavities, for all three answers.
- On plain pairs with a fixed width, the fit matches `choix`'s EP within about 0.1%, which is `choix`'s own error: it approximates the logistic curve by five normal curves.
- The result doesn't depend on the order of the answers or on the starting point, within 1e-8. A session's warm-started fits pass `verify`.

The width learned from the same answers as section 1 (with plain pairs, no ties and no bonus, so that `choix` could be used, and a flat starting belief):

| Judge | True spread | Laplace | EP |
|---|---|---|---|
| normal | 9.58 | 1.92 | 10.13 |
| human | 2.56 | 1.50 | 2.66 |
| perfect | no limit | 2.05 | 58 |

With the full model and the starting belief as shipped, EP's width came out 4.80 (normal), 6.33 (perfect), 3.56 (careless), 2.51 (human) and 2.49 (noisy). The #1 to #4 gap as a share of its true size moved from Laplace to EP as follows: normal 0.52 → 0.94, perfect 0.51 → 1.31, careless 0.36 → 0.51, human 0.86 → 1.04, noisy 1.12 → 1.51.

On random pairs from a Bradley–Terry judge (8 seeds, flat starting belief), EP's width was 0.75–1.00 of the truth at the median, Laplace's 0.30–0.85. One list's width is noisy: one seed came out twice the truth.

The careless judge stays squeezed, because its random answers aren't in the model.

Speed: about 60 ms per fit from scratch on 20 items and 143 answers, and about 40 ms per answer in sessions, against about 4 ms for Laplace. 200 items isn't measured; the goal (G4) is under 50 ms.

## 3. EP in sessions

Rounds until rankify stopped, shipped → EP (median of 10 lists):

| Judge | Quick | Quick, bell curve | Stable | Stable, bell curve |
|---|---|---|---|---|
| perfect | 58 → 44 | 60 → 45 | 102 → 82 | 104 → 79 |
| normal | 70 → 60 | 96 → 76 | 146 → 136 | 162 → 174 |
| careless | 80 → 70 | 89 → 74 | 138 → 146 | 158 → 174 |
| noisy | 108 → 98 | 121 → 108 | 184 → 209 | 180 → 228 |
| human | 105 → 100 | 122 → 120 | 192 → 198 | 202 → 221 |

- Quick stopped sooner for every judge and both shapes.
- Stable got slower for most judges. Guess: Stable's tier cuts and its "reach" rule judge items that are rarely asked about, and those are where honest doubt costs most.
- The target held at the stop in 116 of 120 clear-judge sessions with EP, against 119 of 120. For the human and noisy judges it held in 42 of 80, against 40 of 80.

## 4. Repeated questions

In Quick sessions (20 items), this share of rounds asked a pair that had already been asked:

| Judge | Shipped | EP | Most times one pair was asked (median per session) |
|---|---|---|---|
| perfect | 31% | 24% | 5 → 4 |
| normal | 41% | 40% | 8 → 8 |
| careless | 43% | 45% | 8 → 8 |
| human | 51% | 50% | 14 → 12 |
| noisy | 49% | 51% | 16 → 13 |

- Most repeats came after every earlier answer to that pair had gone the same way: all of them for the perfect judge, 69% for the normal judge.
- The benchmark's wasted-questions table had shown this since Phase 2. Step 3's report gives 79% exact repeats for the human judge on 10 items, against 77% for Elo; that figure counts Exact sessions up to their budget.
- The planner scores a pair by what its answer would teach about the order, and treats every answer as a fresh coin flip. A close pair therefore always looks worth asking again. A person remembers and answers the same way, so the repeat teaches little and wears them out.

**The rule tried first:** a pair the judge has answered comes back only when the fit now orders it against the judge's own answers on it, and at most once (`planner.ASK_AGAIN = "contradicted"`). Only the asking judge's answers count; another judge can still be asked the pair.

Shipped → EP with that rule (benchmark-shaped scores):

| Judge | Quick rounds | Quick right | Stable rounds | Stable right |
|---|---|---|---|---|
| perfect | 58 → 48 | 10 → 10 | 102 → 72 | 10 → 10 |
| normal | 70 → 49 | 10 → 10 | 146 → 84 | 10 → 8 |
| careless | 80 → 49 | 10 → 6 | 138 → 84 | 10 → 2 |
| noisy | 108 → 58 | 7 → 4 | 184 → 106 | 3 → 3 |
| human | 105 → 60 | 9 → 6 | 192 → 108 | 5 → 0 |

"Right" means the mode's target really holds at the stop.

- Repeats fell from 30–51% of rounds to 0–10%.
- No session stopped at its own target. Every one ended at "nothing worth asking", against 38 of 100 that reached the target before.
- The old fit with the same rule was about as accurate, with slightly more rounds.

The repeats were catching slips. A judge who usually answers well but sometimes slips now keeps the slip, unless other answers happen to contradict it, and near the top there are rarely enough of those.

## 5. One re-check per pair, and sorting

The second rule allows any pair one re-check, when the planner finds it worth asking (`ASK_AGAIN = "once"`). It was run with EP against the first rule, shipped rankify, and two sorts, on the same lists. Times are the benchmark's simulated minutes of the person's time.

**Right at the stop, and minutes to the stop** (lists out of 10 · minutes):

| Judge, mode | Shipped | Only if contradicted | One re-check |
|---|---|---|---|
| perfect, Quick | 10 · 2.5 | 10 · 2.1 | 10 · 1.9 |
| perfect, Stable | 10 · 4.9 | 10 · 3.2 | 10 · 3.8 |
| normal, Quick | 10 · 3.0 | 10 · 2.1 | 10 · 2.5 |
| normal, Stable | 10 · 7.7 | 8 · 4.0 | 6 · 4.2 |
| careless, Quick | 10 · 3.8 | 6 · 2.1 | 9 · 2.3 |
| careless, Stable | 10 · 6.7 | 2 · 3.8 | 7 · 5.0 |
| human, Quick | 9 · 5.1 | 6 · 2.7 | 4 · 2.6 |
| human, Stable | 5 · 9.7 | 0 · 5.1 | 0 · 6.1 |
| noisy, Quick | 7 · 5.2 | 4 · 2.5 | 5 · 2.8 |
| noisy, Stable | 3 · 9.1 | 3 · 4.9 | 1 · 5.6 |

- Right at the stop, over all 100 sessions: shipped 84, only if contradicted 59, one re-check 62.
- Repeats: shipped 30–50% of rounds, only if contradicted 0–10%, one re-check 21–26%.
- One re-check helps the careless judge a lot (Stable 2 → 7 of 10, Quick 6 → 9) for about 10–30% more time than the strict rule. It doesn't help the human and noisy judges.
- It still spends re-checks widely: about a quarter of all rounds, on most close pairs, not only on the pairs that decide the result.
- Neither rule comes near shipped accuracy for judges who make mistakes, at about half the time. Both end every session at "nothing worth asking". Guess: the giving-up rules (the 0.1-bit floor and "another look"), tuned with a planner that could repeat, now give up too early.

**Minutes until the target is reached** (the benchmark's rule: it holds from then on; — = not reached in most lists; lists reached in brackets when fewer than 10):

| Judge, mode | Shipped | Only if contradicted | One re-check | Just Sort It | Ford–Johnson |
|---|---|---|---|---|---|
| perfect, Quick | 1.8 | 1.2 | 1.2 | 2.8 | 2.2 |
| perfect, Stable | 2.7 | 1.8 | 2.2 | 5.0 | 3.1 |
| normal, Quick | 1.8 | 1.2 | 1.3 | 4.2 | 2.1 (8) |
| normal, Stable | 3.1 | 2.5 (8) | 2.5 (7) | 5.1 | — (3) |
| careless, Quick | 1.7 | 1.5 (6) | 1.4 (9) | 4.0 (9) | 3.0 (7) |
| careless, Stable | 3.3 | — (3) | 3.5 (7) | 9.2 (9) | — (0) |
| human, Quick | 2.8 (9) | 2.3 (6) | — (4) | 10.9 (7) | — (5) |
| human, Stable | — (5) | — (0) | — (1) | — (3) | — (1) |
| noisy, Quick | 3.0 (8) | — (5) | 1.8 (7) | 8.1 (7) | — (5) |
| noisy, Stable | 8.4 (6) | — (4) | — (2) | — (3) | — (0) |

- **Against Just Sort It:** every rankify version reached each target sooner, usually 2 to 4 times sooner where both got there.
- **Against Ford–Johnson:** with the perfect judge, sorting's best case, every rankify version got there sooner on these lists: with EP, Quick in 1.2 minutes against 2.2 and Stable in 1.8 against 3.1. rankify also stopped by itself (1.9–2.1 minutes for Quick) before Ford–Johnson's order held. Once the judge makes mistakes, Ford–Johnson reached Stable in at most 3 of 10 lists.
- **These lists disagree with step 2's.** On step 2's 20 test lists, Ford–Johnson reached the perfect judge's Quick in 1.1 minutes against rankify's 1.6. "rankify beats Ford–Johnson with a perfect judge" needs the test lists before it can be claimed.
- Times to the target use knowledge of the truth. A sort doesn't know when it is done; rankify stops by itself, so its stop time is the fair practical number.

## Conclusions

- The over-doubt comes from the Laplace fit, not from the starting belief. EP learns the spread about right, at about ten times Laplace's cost.
- Repeats were a third to a half of all questions. Cutting them roughly halves a session, but some re-asking is needed for people who slip, and neither rule tried keeps shipped accuracy. Guess: what works is re-checking only the pairs that decide the result, plus a stop rule that knows when the result is right instead of giving up.
- rankify beats Just Sort It by a wide margin and beats Ford–Johnson as soon as the judge makes mistakes. With a perfect judge the two list sets disagree.

## Open decisions

- **How to re-check.** Neither "only when contradicted" nor "one re-check per pair" keeps accuracy for judges who slip. Next candidate: re-check only pairs that decide the mode's target.
- **Whether a pair answered once, with nothing against it, counts as settled.** Without repeats rankify can't become 90–95% sure of a neighbour pair. With either rule on, three planner tests that expect "target reached" with a perfect judge fail, though those sessions end with the right order.
- **The stop test.** Stable with EP is slower for most judges, and without repeats every session gives up instead of reaching its target. The planned stop test (stop when the mode's whole target holds in 90% of the posterior draws) is meant to address both.
- **EP's speed** at 200 items.
- **Ford–Johnson with a perfect judge**, on the test lists.

## How it was run

Every number here comes from a script in [2026-10-14-step4/](2026-10-14-step4/), which lists each script's arguments and keeps its output. The session comparisons call `bench.run_one` with switches set in each worker: `service.EP_FIT` for the fit and `planner.ASK_AGAIN` for repeats (`"always"` is the shipped behaviour). The diagnostics in section 1 replay the same sessions and read the fit after every answer.
