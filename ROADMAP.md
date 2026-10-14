# Roadmap

Each phase ends with a check. We write down what we found, and whether we continue as planned, change the plan, or stop. Benchmark results are recorded in [EXPERIMENT.md](EXPERIMENT.md). Goal numbers refer to [GOALS.md](GOALS.md).

## Phase 0: Proposal and design ✅

We wrote the proposal, philosophy, design, goals, experiment plan, roadmap and CLI reference, and created the public repository.

## Phase 1: Foundations ✅

This phase builds the parts everything else rests on, for pair rounds only:

- the Python project, with uv, Typer, numpy, pytest and Hypothesis
- the SQLite store: the answer log, the derived tables, and migrations
- the engine: Bradley–Terry with ties and position bias, the prior, the fit, the ranges, and Score, Confidence and Could be
- the first commands: `new`, `add`, `next` (random pairs for now), `answer`, `undo`, `show` and `verify`, all with `--json`
- tests: shuffling the log, the comparison with `choix`, replay, and speed tests for saving and refitting

**Check:** sanity checks 1, 2 and 4 in [EXPERIMENT.md](EXPERIMENT.md#sanity-checks-first) pass, and a refit takes under 10 ms for 200 items.

**Result (2026-10-11):** passed. Our fit matches `choix` within 1e-4. Shuffling the answers changes no number by more than 1e-9 (60 Hypothesis cases). Replay gives the same rounds. A warm refit takes 4.0 ms for 200 items and 2,000 answers, and answer to next round takes 16 ms (95th percentile) for 200 items. In a quick check with a simulated judge (15 items, 30 runs, random pairs), the median Kendall tau rose from 0.50 after 25 rounds to 0.87 after 300. The expected calibration error of Confidence was 0.047. Could be held the true rank 94–98% of the time, which is wider than the 90% it claims. The full benchmark in Phase 2 will check both properly.

Two things were left for Phase 2. The prior width is fixed at `sigma = 1.5` and is not yet learned from the judge's consistency. Random pairs take many rounds to find the true #1 (77% after 300 rounds), which is the planner's job.

## Phase 2: Planner and benchmark, pairs only ✅

This phase builds:

- the planner: BALD gain per second over pair candidates, the "nothing worth asking" floor, and saved plans
- the prior width learned from the judge's consistency, in place of the fixed `sigma = 1.5`
- the stopping rules for Quick, Stable and Exact
- the simulator, with all nine judges and simulated time
- the baselines: Elo (random and close pairs), random pairs with our fit, openskill, merge-insertion sort, and Just Sort It
- the `sim` and `why` commands

**Done early (2026-10-12):** `rankify bench`, which drives every method through the CLI against a simulated human judge. The baselines are rating systems built for human judges, available as `--method` options: `elo`, `elo-close`, `glicko2`, `trueskill`, `openskill` and `arena`. Two sorts (`just-sort-it`, `insertion-sort`) run as reference lines. The [human-judge report](experiments/2026-10-12-human-judge.md) sets the bar for the planner:

- **Wasted questions.** About 90% of rankify's questions were already answered by earlier answers. The same holds for every rating system, because they all ask random pairs. This is the planner's main opportunity.
- **Today rankify is level with the rating systems, not ahead.** On 20 items it reached Quick in 259 rounds; Glicko-2 needed 126 and Elo 315. That is far from the goal of a third of Elo's time (G1).
- **Exact is out of reach for a human judge on 20 items.** No method got there. That supports precision modes, where Quick and Stable are the realistic targets.
- **Confidence is calibrated with the human judge** (error 0.017–0.032). With a perfect judge it is still too cautious (0.12–0.13), so the prior width should be learned from each judge's consistency.
- **The human judge's settings are guesses.** A calibration session replaces the ones it can measure (see Phase 5).

**Check:** run the pairs-only part of the grid. What happens next depends on the result:

- If the planner beats Just Sort It by at least 20% in time (G2), continue to Phase 3.
- If it beats Elo but not Just Sort It, use Just Sort It's way of picking questions with our fit, and re-plan Phase 3 around it.
- If Confidence isn't calibrated (G5), fix the model or the prior before anything else.

**Result (2026-10-12): passed for Quick, mixed for Stable; continue to Phase 3.**

What was built:

- The planner picks pairs by order information per second, weighted by how much each pair matters for the mode. Every item gets first looks, and the stopping rules include a Could be check and an 8-answer floor.
- The prior width is learned from the answers.
- `why`, `next --mode` and `play --mode` were added.
- The benchmark took the place of a separate `sim` command, with three judges (human, perfect, noisy) instead of nine.

The [v1](experiments/2026-10-12-phase2-planner-v1.md) and [v2](experiments/2026-10-12-phase2-planner-v2.md) reports, and the tuning between them, are summarized in [EXPERIMENT.md](EXPERIMENT.md#results). Against the checks above:

- **Confidence is calibrated:** error 0.038–0.049.
- **G2 (beat Just Sort It by 20%) holds for Quick:** 52% of its time on 20 items and 76% on 10. It does not hold for Stable on 10 items (95%).
- **G1 (half of Elo's time) holds for 20-item Quick (23%)** but not on 10 items: 66% for Quick and 67% for Stable.

Phase 3's questions about 3–5 items are the main lever for the 10-item gap. One ordering settles several neighbour pairs at once, and that should also cut the confirmation rounds after the ranking is already right.

## Phase 3: Mixed rounds

This phase adds:

- pick and rank rounds with Plackett–Luce, up to 5 items
- candidate sets of 3 to 5 items, keeping near-duplicates out of pick rounds
- a timing model for each judge

**Check:** run the full grid, including the half-time and double-time runs. If mixed rounds don't save time (G3), ship pairs only and keep mixed rounds behind a flag.

**Result (2026-10-12): G3 not met. Pairs stay the default, and mixed rounds ship behind `new --rounds mixed`.**

What was built:

- Pick and rank rounds of 3 to 5 items, fitted with pairs in one Plackett–Luce model. The fit matches `choix` and stays independent of answer order.
- A mixed planner. It grows sets from the best pairs and scores them by the information about their order from neighbour pairs, per second, with per-kind timing that learns your own times.
- `new --rounds`, answers like `3142`, multi-key `play`, and `why` for sets.
- In the benchmark: the mixed variant, the round mix, goal G8 at each stop, and `--set-time-scale`.
- Answer→next stays fast with mixed rounds: p95 42.5 ms at 200 items (G4). The planner now reuses the fit that `answer` just made.

How mixed rounds compare with pairs only, as a share of the time to each target (human judge, 20 lists; [main report](experiments/2026-10-12-phase3-mixed-rounds.md), [half](experiments/2026-10-12-phase3-set-time-half.md), [double](experiments/2026-10-12-phase3-set-time-double.md)):

- **Pick and rank times as guessed:** 10-item Quick 74%, 10-item Stable 121%, 20-item Quick 108%.
- **Half the guessed time:** 33%, 75% and 45%.
- **Twice the guessed time:** 158%, 139%, and 20-item Quick not reached in most lists.

So the outcome depends on how long a person really takes to order a few items, which nobody has measured yet. In the benchmark's judge, ordering k items costs as much as asking its k − 1 neighbour pairs one at a time. An ordering then teaches about as much per second as pairs, and it gives up choosing each next question from the latest answer. With the perfect judge, mixed rounds were faster in 4 of 6 settings, equal in 1 and slower in 1.

Pairs only, as shipped, against the baselines in the same run:

- **10 items:** Quick 64% of Elo's time and 75% of Just Sort It's. Stable 66% and 94%.
- **20 items:** Quick 26% of Elo's time and 57% of Just Sort It's.
- **Calibration:** error 0.043–0.048 (G5).

Lessons:

- **A first version counted every pair in a set,** which counted the same information about twice. It chose orderings for about 90% of rounds and was slower than pairs on the tuning lists. Counting only neighbour pairs fixed the measure, but not the outcome.
- **The stopping rules settle each neighbour pair, while the benchmark's targets need the whole order.** So "target really met at the stop" is lower than each pair's confidence suggests: 19 neighbour pairs at 95% each are all right only about 38% of the time. The report now also shows G8, which is defined per pair. With mixed rounds, Exact on 20 items stopped with 78% of pairs right, short of G8's 95%.
- **Reproducibility:** 11 of 36 cached Phase 2 runs don't come out the same from the committed Phase 2 code. They were probably saved by an earlier state of the code during Phase 2. The committed Phase 2 code and today's pairs-only planner agree on every list checked. This benchmark reran everything from scratch.

Next: Phase 5's pilot measures how long ordering really takes. If people are clearly faster per item than with pairs, rerun G3 with those times and reconsider the default.

## Phase 4: Rounds left, terminal UI and report

This phase adds:

- the background forecast, and tests of its coverage (G7)
- the Textual terminal UI: typing the order or moving items, can't decide, undo, and the ranking view
- the agent report, in Markdown and JSON
- the speed targets, enforced end to end (G4)

**Check:** a full session on a 20-item list in the terminal UI, with no visible wait between rounds, and forecast coverage within target in simulation.

**Result (2026-10-12): the UI and the report pass; the forecast meets G7 only in part.**

What was built:

- `rankify forecast` and rounds left in `next`. The forecast plays the session forward in simulation, with a closed-form update after each simulated answer (see [DESIGN.md](DESIGN.md#rounds-left)). It is saved and reused until the list changes.
- `rankify play` as a Textual terminal UI: number keys, arranging an ordering with ↑ ↓ and Space, can't decide, undo, and the ranking view. The forecast runs between keypresses. `--plain` keeps the old line-by-line reader.
- `rankify report`, in Markdown or JSON: ties, weak spots, slow decisions, upsets, the judge's habits, and disagreements between judges.
- `--json` on every command that prints results (G11), and G7 in the benchmark.

Against the check ([report](experiments/2026-10-12-phase4-forecast.md)):

- **No visible wait (G4):** in a headless 20-item session, the next round is drawn 3.5 ms after the answer key (p95 3.6 ms). A key reaches the UI within 1 ms while a forecast runs. Answer → next round at 200 items with mixed rounds: p95 38 ms. These are simulated sessions, not a person at a terminal.
- **Forecast coverage (G7), human judge, pairs as shipped:**
  - **20 items:** met. The 10–90% range held the rounds really left 78% of the time (Quick) and 89% (Stable). The median was off by 22% and 14%.
  - **10 items:** just short at 67% and 68%, with the median off by 20% and 16%.
  - **Exact:** not met: 32% on 10 items, and on 20 items no session finished, so it can't be scored.
- **Where the forecast fails:**
  - **Mixed lists:** the simulation asks pairs only, so it forecasts 1.3 to 2 times too many rounds.
  - **A perfect judge:** early forecasts assume answers as noisy as the model's prior, so they run far too long.
  - **Human answers:** the simulated judge never slips, tires or says "can't decide", which is likely why the human-judge ranges run a little narrow.

Found in review and fixed before the benchmark:

- The forecast's stop check used an approximate normal curve, which moved the 95% and 80% thresholds enough to change when simulations stopped.
- The forecast didn't pause between simulations, so the UI could wait for it.
- "Slow decisions" compared orderings with pairs.
- `play` crashed on a list with fewer than 2 items.

Next: simulating picks and orderings in the forecast, and a judge with slips and fatigue, would address the misses. The human pilot (Phase 5) comes first, because it also measures how long ordering really takes.

**Follow-up (2026-10-12): the forecast for mixed lists.** Done alongside the pilot rather than after it.

What changed (see [DESIGN.md](DESIGN.md#rounds-left)):

- The simulation asks picks and orderings too, chosen with the real planner's code.
- Its judge says "can't decide" at the rate the fit learned for the list, and tires as a sitting goes on. A pause of more than 30 minutes starts a new sitting.
- Each simulation draws the prior width from what is known about it, and redoes the fit for that width.
- Simulated slips were tried and dropped: the fit already accounts for them, and adding them made forecasts run long.
- `forecast` and `report` take `--judge`, since the forecast now uses each judge's own times.

Against G7 ([report](experiments/2026-10-12-forecast-mixed.md); human judge, 20 lists per setting):

- **Pairs, Quick and Stable:** met at both sizes, for the first time. The range held 76% and 89% (Quick, 10 and 20 items) and 81% and 78% (Stable), and the median was off by 14–24%. In Phase 4: 67–89%, with medians off 14–22%.
- **Mixed lists, Stable:** met on 20 items (range held 77%, median off 25%). On 10 items the range held 91%, just over the target's 90%, with the median off 15%. In Phase 4: 23–26% and 132–148%.
- **Mixed lists, Quick:** the range held 79% and 80%, but the median was off by 42% and 41%. Not met.
- **Mixed lists, Exact:** the range held 62% and 53%, the median was off by 35% and 29%. Not met, though Phase 4 held 0–6%.
- **Pairs, Exact:** the range held 43% on 10 items; on 20 items no session finished within the round budget, so it can't be scored.
- **Perfect judge:** still fails (range 0–39%, medians off 85–248%). The forecast assumes answers as noisy as the fit says, and a perfect judge is not.

On a fresh list the low end of the range can sit far below the median, as in "72 (12–99)". That is the model allowing that the items might be nearly tied, in which case the real fit also learns a narrow spread and stops early. Clipping it would be arbitrary, and coverage was worse without the width draws.

Found in review and fixed before the final benchmark:

- A single Newton step per pick, ordering or "can't decide" overshot when the answer surprised an unsure fit; a "can't decide" could swap the two items. Each update now finds the mode of the shown items.
- Fatigue counted every answer ever given on the list, so it never reset between sittings.
- `forecast` and `report` always used the judge "me".

**Follow-up 2 (2026-10-12): the open items.** Same [report](experiments/2026-10-12-forecast-mixed.md), rerun.

What changed (see [DESIGN.md](DESIGN.md#rounds-left)):

- The simulated fit learns its width again from the simulated answers, as the real fit does.
- The simulated judge is as decisive as the real one has been: a calibration slope of their answers against what rankify expected before each.
- A simulation may run to 50 rounds per item instead of 20, so long Exact sessions get a number instead of "at least".
- The information of an ordering is computed stage by stage with each choice laid out by item: the same numbers, 2.3–2.8 times faster, so mixed forecasts run 6–25 simulations instead of 5–17.

Against G7, human judge (10 and 20 items):

- **Met:** pairs Stable (range held 73% and 72%, median off 16% and 18%); pairs Quick on 20 items (81%, 16%); mixed Stable (83% and 79%, off 18% and 20%).
- **Just short:** pairs Quick on 10 items, range held 69% (median off 20%).
- **Not met:** mixed Quick, where the median is off by 36% and 29% (from 42% and 41%), and mixed Exact (range held 68% and 55%, median off 31% and 24%). An earlier run of this follow-up, before the review fixes below, had mixed Quick on 20 items just inside (24%); reading orderings correctly for the judge's sharpness moved it back out.
- **Pairs, Exact:** with 60 rounds per item every session finished; the range held 71% and 65%, the median off by 11% and 5%. With the usual 20 per item, 20-item sessions run out before they finish, so the main report can't score them.
- **Fresh lists:** the low end of the range no longer drops far below the median ("89 (60–116)" where it was "72 (12–99)").
- **Perfect judge:** not fixed (range held 0–58%, medians off 51–200%). Even when the forecast is told the judge is nearly perfect, it runs 33–97% long: with no contradictions, the real fit spreads the scores faster than the simulated fit.

Found in review and fixed: the judge's sharpness read an ordering as its neighbouring pairs, which under Plackett–Luce makes a judge who follows the model look 25–45% less decisive; re-learning the width left out removed items, which the real fit counts; and the width could change halfway through planning a simulated round.

Tried and dropped: predicting set times from the first few timed answers. Given the times each session ended up measuring, 20-item mixed forecasts would run 3% long on Quick instead of 16%. But the prediction from early answers didn't help, because much of the shift comes from the pair time, which mixed sessions measure last.

Speed: unchanged for the planner (answer → next round at 200 items with mixed rounds: median 31 ms, p95 34 ms). In the terminal UI on a 20-item mixed list, a key reaches the UI within 1 ms while a forecast runs, and the next round is drawn 25 ms after the answer key (p95 31 ms).

Why mixed forecasts still run high: real sessions shift toward orderings as the judge's measured times replace the guesses (on the benchmark's judge, ordering 4 items took 2.2–2.8 typical pairs against the guessed 3), and pair times stay at their default because mixed sessions ask so few pairs. The simulation can't foresee times not yet measured. In the forecast's own simulations, pairs are 25–40% of rounds; in real sessions, 8–16%.

Speed: a mixed forecast fits about 5 to 15 simulations into its 0.8 s budget, against about 10 to 60 for pairs. In the terminal UI on a 20-item mixed list, a key reaches the UI within 11 ms while a forecast runs (median 0.5 ms), and the next round is drawn 26 ms after the answer key (p95 30 ms), the cost of planning sets, not of the forecast. (A headless test's "key to next round" reads about 0.9 s, but that is Textual's test pilot waiting up to a second for the process to go idle while the forecast keeps it busy.)

## Engine check: the full judge grid

The engine comes before any interface: it should meet G1–G12 on a benchmark wider than one guessed human judge, or explain each miss, before a browser UI, a website or servers. This check fills in the grid EXPERIMENT.md planned for Phase 2, at a size this machine runs in a few hours.

**Step 1 (2026-10-13): measure.** Built: the six missing judges (sharp, normal, fuzzy, careless, biased, thurstone, similar and tired, with the existing human, perfect and noisy), Ford–Johnson merge insertion as a reference sort, and two planner variants that check rankify's design (`rankify-closest`, `rankify-per-round`). Reports: [all judges](experiments/2026-10-12-judges-grid.md) (10 and 20 items, 20 lists each, 4,400 runs), [planner variants](experiments/2026-10-12-planner-variants.md), [50 items](experiments/2026-10-12-fifty-items.md) (human and normal judges, 10 lists each). The 100-item lists and 100 seeds per setting are left out: they would take days here.

What it shows, for rankify on pairs:

- **Model violations don't hurt it.** With judges who answer 5% at random, favour the first item, use a different noise curve, split votes between near-twins, or tire, rankify's Quick and Stable stops met their target in 15–20 of 20 lists on 20 items, with G8 at 95–100%. (Exact stops less often on 20 items within the budget; with the tired judge it met its target in 2 of the 6 lists that stopped.)
- **G1 (half of Elo's time) holds wherever the judge tells neighbours apart 75% of the time or better**: 16–48% of Elo's time across sharp, normal, careless, biased, thurstone, similar and tired, at both sizes. It misses with the low-accuracy judges (human, noisy and fuzzy, 57–60%) on 10 items (55–79%), and with the noisy judge on 20 items, where rankify reached Quick in only 10 of 20 lists.
- **G2 (80% of Just Sort It's time) mostly holds on 20 items**: 30–72% for the clearer judges, and 56–62% on Quick for the human and fuzzy judges. It misses for fuzzy Stable (100%) and similar Exact (90%). On 10 items rankify is about level with Just Sort It (48–106%).
- **G5 (calibration) holds**: error 0.014–0.051 across 22 judge and size settings (one at 0.051). **G6 (Could be) doesn't**: it held the true rank 95–100% of the time almost everywhere, wider than the 85–95% it should be.
- **G9 (order doesn't matter)**: the #1 never changed when answers were replayed in another order (0 of 440 lists; Elo 44 of 440).
- **Mixed rounds (G3)**, at the guessed set times, are faster for the clearer judges in Stable and Exact (65–99% of the pairs time on 20 items) and on 10 items in most modes; on 20-item Quick they are slower for four of the seven (101–125%). Still decided by real times.
- **Planner variants.** Order information against the pair closest to 50/50: on 20 items the 50/50 planner reached the targets far less often (Stable with the normal judge in 6 of 20 lists against 19; with the careless judge 3 against 20), though on 10 items it was sometimes quicker when it got there. Information per second against per round made no measurable difference on pairs, whose answer times vary little; it matters for choosing between pairs and orderings.
- **Ford–Johnson** is the fastest sort for a perfect judge (Exact on 20 items in 62 rounds; rankify 81, mixed 22) and loses lists as answers get noisy: with the normal judge it reached Stable in 12 of 20 lists on 10 items and 8 of 20 on 20 items, and with the human judge 4 and 0.

**Where the engine is weak:**

- **Lists of 50 items, on pairs.** With the human judge, the Quick stop came at about 90 rounds with the true #1 on top in only 7 of 10 lists (G8 asks 9 of 10). With the normal judge it put the #1 right but the top 3 wrong, so Quick was really reached in only 4 of 10 lists. Mixed rounds reached Quick in 10 of 10. A likely cause is that two first looks per item aren't enough to rule an item out among 50.
- **Low-accuracy judges stop Stable early.** On 20 items, Stable stopped with 85% (human) and 83% (noisy) of the top pairs right, against the 90% G8 asks.
- **Could be is too wide** (G6), above.
- **Small lists with a low-accuracy judge**: G1 and G2 miss on 10 items for human, noisy and fuzzy.

Step 2 fixes these, then the benchmark runs again.

**Step 2 (2026-10-13): fixes, and rounds left as a formula.** Reports: [all judges](experiments/2026-10-13-step2-judges.md), [50 items](experiments/2026-10-13-step2-fifty-items.md), the same lists as step 1.

Changed:

- **Another look before giving up.** When the floor would stop the session, an item still in play with fewer than 6 answers first gets another look (see DESIGN.md, Stopping). On long lists the chance of belonging to the top was spread thinly over many barely seen items, so no single pair looked worth asking while the top was still open.
- **Could be** is now the narrowest run of ranks holding 90% of the draws. The stopping rules keep the wider central range as a margin; with the narrower one, Stable stopped earlier with the human judge.
- **Rounds left is a formula, not a simulation.** Each pair the mode still needs gets a closed-form count of the answers it will take, over 64 draws of the true scores (see DESIGN.md, Rounds left). A forecast takes about 8 ms instead of up to a second, gives the same answer every time, and is cheap enough to follow every answer at public scale.

What the benchmark shows, for rankify on pairs:

- **50 items, normal judge:** Quick was really met at the stop in 10 of 10 lists, against 4 of 10 in step 1.
- **50 items, human judge:** Quick was really met at the stop in 3 of 10 (step 1: 1), with the true #1 on top in 8 of 10 (step 1: 7). G8 asks 9 of 10, so this is still a miss.
- **20 items:** Quick was really met at the stop in 13 of 20 lists with the noisy judge (step 1: 10) and 17 of 20 with the fuzzy judge (step 1: 15). Other settings didn't change.
- **Rounds left (G7)** held in more settings than before in 41 of 44 settings. Stable held 80–89% for most judges, Quick 82–92% for the human, noisy and fuzzy judges, and on 50 items 98–100%. Mixed lists held 73–95%. In step 1 most settings held 13–82%.
- **Could be (G6)** held the true rank 92–100% of the time, and 86% for the human judge on 20 items: still too wide for the clearer judges.

Still open:

- **Forecasts for clear judges run long early.** Quick held only 49–66% for the sharp, normal and Thurstone judges, with the median 60–90% too high, and 10–40% for the perfect judge. Early on, the fit's width and the judge's sharpness both read low, so the forecast takes a decisive judge for an ordinary one. Carrying a judge's sharpness from one list to the next would help returning judges.
- **Late in Stable sessions** forecasts run about 30% short: the "another look" rounds aren't counted.
- **Stable stops early for low-accuracy judges:** on 20 items it stopped with 87% (human) and 83% (noisy) of the top pairs right, against the 90% G8 asks.
- **G1 on 10 items with low-accuracy judges** still misses. Pairs can't tell such judges' items apart much faster; this is accepted as a limit of pairs.

**Step 3 (2026-10-14): the judge's sharpness, and a faster benchmark.** Report: [gap scale](experiments/2026-10-14-step3-gap-scale.md), with the human, noisy, normal and perfect judges on 10 and 20 items, 50 lists each. Elo and Just Sort It came from step 2's runs.

Changed:

- **The forecast draws the judge's sharpness from what the answers say about it.** While they say little, the range covers both an ordinary and a decisive judge. On the saved sessions the range held 2–8 points more often; medians barely moved.
- **The fit's gaps are widened by the sharpness the answers surely show** (see DESIGN.md, Fitting). Widening by the whole reading cut clear judges' sessions by 30–50%, but it stopped error-prone judges early: on 20-item Quick lists the human judge's true #1 was on top in 43 of 50 lists instead of 49. The lower 90% bound keeps part of the gain and leaves the error-prone judges as they were.
- **The benchmark calls the service layer.** It now runs the functions the CLI and the terminal UI call, in one open session, instead of running each CLI command. Command parsing, JSON and reopening the database had taken most of the time: 1,200 runs took 325–395 s instead of 957 s. Sessions don't match the CLI-driven ones round for round. Refitting in another order changes scores in the 13th digit, and that breaks exact ties between items not yet asked about differently. Over 50 lists per setting, the two drivers agree (medians within 4 rounds).

What the benchmark shows, on 20 items, against the same lists without the gap scale:

- **Normal judge:** Quick took 66 rounds instead of 76, Stable 144 instead of 176, and Exact 361 instead of 370. Targets were met at the stop as often as before (Stable 47 of 50, from 48).
- **Perfect judge:** Quick took 58 rounds instead of 62, Stable 104 instead of 129, and Exact 180 instead of 244. All were met.
- **Human and noisy judges:** rounds within 5 of before, with the same accuracy at the stop. The human judge's Quick still has the true #1 on top in 49 of 50 lists, and Stable has 86% of top pairs right (from 87%).
- **10 items:** little change, except the normal judge's Exact (130 rounds instead of 146).

Looked at and left as is:

- **Scale.** At 200 items, an answer takes about 29 ms to the next round: about 12 ms for the Could be draws, 9 ms for the refit and 3 ms for planning. A closed-form rank distribution matched the draws but was slower at 200 items (27 ms against 11), so the draws stay for lists of up to 200 items.
- **Stable stops early for low-accuracy judges.** Asking more before giving up (a lower floor) raised the noisy judge's top pairs to 97% right, but it took 50% more rounds; the human judge stayed at 87–90% with 50–95% more rounds. It is a trade of time for accuracy, and the floor stays.

Still open:

- **Could be (G6)** is still too wide for the clearer judges: 98–100% coverage against 85–95%. The compressed fit is the cause, and the gap scale did not change it.
- **The sharpness reading** ignores how the scores of two compared items move together, which raises it by about 0.1–0.2.
- Forecasts for clear judges still run long early, and late in Stable sessions they run short (see step 2).

## Phase 5: Human pilot

**Done early (2026-10-12):** the calibration tools are built: `new --calibrate`, a minimal `play`, `calibrate`, and `bench --judge-profile`. The first real calibration session comes next, before Phase 2.

**Ready for the pilot (2026-10-12):** `calibrate` learns from several lists at once and measures how long picks and orderings take next to the judge's pace on pairs (`set_time_scale`, used by `bench --judge-profile`). On simulated judges it reads about 10% low. `export` writes a list as JSON lines, as a backup; `rebuild` refits after an upgrade and shows what moved; `show --tiers` groups the ranking into settled tiers.

- Rank three real lists: travel (about 20 items), products (about 10) and restaurants (about 15).
- Replace the timing guesses with measured times, and rerun the Phase 3 comparison.
- Fix whatever feels wrong.

**Check:** each final ranking needs only a few manual moves, and the measured times don't reverse the Phase 3 decision.

## Phase 6: Many judges, locally

This phase adds:

- sessions for each judge
- a hierarchical model: a shared score plus each judge's offset
- equal weight for every judge
- merging logs from several files
- personal rankings that start from the shared one
- a report section on where judges disagree

**Check:** G12 holds. Merging gives the same result in any order, and a heavy voter doesn't dominate.

## Later

To be discussed once Phase 6 is done:

- remote and public rankings: syncing the log, accounts, and protection against fake votes
- a browser UI that ports the engine, with the Python version as the reference
- taste with more than one axis
- a package name and a PyPI release
