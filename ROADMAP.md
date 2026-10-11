# Roadmap

Each phase ends with a check. We write down what we found, and whether we continue as planned, change the plan, or stop. Benchmark results are recorded in [EXPERIMENT.md](EXPERIMENT.md). Goal numbers refer to [GOALS.md](GOALS.md).

## Phase 0: Proposal and design ✅

We wrote the proposal, philosophy, design, goals, experiment plan, roadmap and CLI reference, and created the public repository.

## Phase 1: Foundations

This phase builds the parts everything else rests on, for pair rounds only:

- the Python project, with uv, Typer, numpy, pytest and Hypothesis
- the SQLite store: the answer log, the derived tables, and migrations
- the engine: Bradley–Terry with ties and position bias, the prior, the fit, the ranges, and Score, Confidence and Could be
- the first commands: `new`, `add`, `next` (random pairs for now), `answer`, `undo`, `show` and `verify`, all with `--json`
- tests: shuffling the log, the comparison with `choix`, replay, and speed tests for saving and refitting

**Check:** sanity checks 1, 2 and 4 in [EXPERIMENT.md](EXPERIMENT.md#sanity-checks-first) pass, and a refit takes under 10 ms for 200 items.

## Phase 2: Planner and benchmark, pairs only

This phase builds:

- the planner: BALD gain per second over pair candidates, the "nothing worth asking" floor, and saved plans
- the stopping rules for Quick, Stable and Exact
- the simulator, with all nine judges and simulated time
- the baselines: Elo (random and close pairs), random pairs with our fit, openskill, merge-insertion sort, and Just Sort It
- the `sim` and `why` commands

**Check:** run the pairs-only part of the grid. What happens next depends on the result:

- If the planner beats Just Sort It by at least 20% in time (G2), continue to Phase 3.
- If it beats Elo but not Just Sort It, use Just Sort It's way of picking questions with our fit, and re-plan Phase 3 around it.
- If Confidence isn't calibrated (G5), fix the model or the prior before anything else.

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
