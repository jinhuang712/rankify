# Roadmap

Each phase ends at a gate. A gate is a check with a written outcome: what we found, and whether we continue as planned, change the plan, or stop. Results are recorded in [EXPERIMENT.md](EXPERIMENT.md).

## Phase 0: Proposal and design ✅

- PROPOSAL, GOALS, DESIGN, EXPERIMENT, ROADMAP and README written.
- Public repository created.

## Phase 1: Foundations

Build the parts everything else rests on, for pair rounds only.

- Python project with uv, Typer, numpy, pytest and Hypothesis
- SQLite store: source-of-truth tables, derived tables, migrations
- Engine: Bradley–Terry with ties and position bias, the prior, Newton fit, uncertainty, Score, Confidence and Could be
- CLI: `new`, `add`, `next` (random pairs for now), `answer`, `undo`, `show`, `verify`, with `--json`
- Tests: the shuffle property, the `choix` comparison, replay, and performance tests for save and refit

**Gate 1:** sanity checks 1, 2 and 4 in [EXPERIMENT.md](EXPERIMENT.md#sanity-checks-before-the-full-grid) pass. Refit takes < 10 ms at 200 items.

## Phase 2: Planner and benchmark, pairs only

- Planner v1: BALD gain per second over pair candidates, the gain floor, and `plans` records
- Stop rules for Quick, Stable and Exact
- Simulator: true scores, all nine judges, simulated time
- Baselines: Elo (random and close pairs), random pairs with our fit, openskill, merge-insertion sort, and Just Sort It
- `rankify sim` and `rankify why`

**Gate 2:** run the pairs-only part of the grid.

| If | Then |
|---|---|
| The planner beats Just Sort It by ≥ 20% in seconds (G2) | Continue to Phase 3 |
| The planner beats Elo but not Just Sort It | Use Just Sort It's selection with our fit, and re-plan Phase 3 around it |
| Confidence is not calibrated (G4) | Fix the model or the prior before anything else |

## Phase 3: Mixed rounds

- `pick` and `rank` rounds with Plackett–Luce, up to 5 items
- Candidate sets of 3 to 5 items, with the near-duplicate rule
- Per-judge timing model

**Gate 3:** run the full grid, including the timing sensitivity runs. If mixed rounds don't save time (G3) under the default and the half/double timing models, ship pairs only and keep mixed rounds behind a flag.

## Phase 4: Rounds left, terminal UI, and report

- Forecast in a background thread, and its coverage tests (G6)
- Textual terminal UI: answer by typing the order or by moving items, plus can't decide, undo, and the ranking view
- Agent report in Markdown and JSON
- Performance budget enforced end to end (G7)

**Gate 4:** a full session on a 20-item list from the terminal UI, with no visible wait between rounds. Forecast coverage is within target in simulation.

## Phase 5: Human pilot

- Rank the three real lists: travel (about 20 items), products (about 10), restaurants (about 15)
- Replace the timing defaults with measured times, then rerun the Gate 3 comparison
- Fix what feels wrong

**Gate 5:** for each list, the final ranking needs few manual moves, and the measured times don't reverse the Gate 3 decision.

## Phase 6: Many judges, local

- Judges in the data model are used for real: per-judge sessions
- Hierarchical model: a consensus score plus a per-judge offset
- Equal judge weight
- Merge logs from several files
- A personal ranking that starts from the consensus
- Report: where judges disagree

**Gate 6:** G12 holds. Merging is order-independent, and a heavy voter doesn't dominate.

## Later

To be discussed when Phase 6 is done:

- Remote and public rankings: syncing the append-only log, accounts, and protection against fake votes
- Browser UI: port the engine, with the Python version as the reference
- Taste with more than one axis
- Package name and PyPI release
