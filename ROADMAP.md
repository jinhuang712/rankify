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

## Phase 4: Rounds left, terminal UI and report

This phase adds:

- the background forecast, and tests of its coverage (G7)
- the Textual terminal UI: typing the order or moving items, can't decide, undo, and the ranking view
- the agent report, in Markdown and JSON
- the speed targets, enforced end to end (G4)

**Check:** a full session on a 20-item list in the terminal UI, with no visible wait between rounds, and forecast coverage within target in simulation.

## Phase 5: Human pilot

**Done early (2026-10-12):** the calibration tools are built: `new --calibrate`, a minimal `play`, `calibrate`, and `bench --judge-profile`. The first real calibration session comes next, before Phase 2.

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
