# Design

This document has two parts. The principles come first: rules that every change must keep, each with the check that proves it. The design that follows from them comes second.

## Principles

| # | Principle | What it means | How we check it |
|---|---|---|---|
| 1 | **One source of truth** | The `rounds` table is the only record of what happened. It is append-only: undo and corrections are new rows. Fits, plans and forecasts are derived and can be rebuilt at any time. | `rankify verify` rebuilds every derived row from `rounds` and compares. |
| 2 | **Same answers, same result** | Scores depend only on the set of answers, never on their order or timing. An answer from the first minute counts exactly as much as one from the last. | Property test: shuffle the rounds, refit, and every score matches within 1e-9. |
| 3 | **An answer is evidence, not fact** | No single answer can lock an order forever. How much an answer counts depends on how consistent this judge has been. | Simulated judges with careless clicks still reach the right ranking. |
| 4 | **Every round earns its place** | The planner picks each round by expected information gain per second, for the current mode. A round whose expected gain is below the floor is never asked. | `rankify why` shows the gain for any round. The benchmark counts wasted rounds. |
| 5 | **Honest numbers** | Every score has a range. Confidence is calibrated: when it says 90%, it is right about 90% of the time. Rounds left is always a range, never a bare number. | Calibration tests in [EXPERIMENT.md](EXPERIMENT.md). |
| 6 | **Instant** | From answer to next round takes under 50 ms (95th percentile, up to 200 items). Slow work runs in the background and never blocks the next round. | Performance tests that fail when a step goes over its target. |
| 7 | **Proven math in the core** | The model is Bradley–Terry / Plackett–Luce. We do not invent a scoring model. New ideas go in the planner, where they can be measured. | Our fits match the `choix` library on shared test data. |
| 8 | **Reproducible randomness** | All randomness (item choice tie-breaks, display order, simulations) comes from a seeded generator, and each round stores its seed. | Replay test: the same seed and answers produce the same rounds. |
| 9 | **Control bias** | Items are shown in random order. Each round logs what was shown and where. The model estimates position bias and removes it. | A simulated judge who favours the first slot still gets the right ranking. |
| 10 | **Judges are equal** | One judge's many votes must not silently outweigh many judges' few votes. Consensus and personal rankings are separate outputs. | Multi-judge tests (Phase 6). |
| 11 | **Every decision is explainable** | The planner stores the candidates it weighed, their gain and cost, and its pick. | `rankify why <round>`. |
| 12 | **Plain words on screen** | The UI says Score, Confidence, Could be, Round and Rounds left. Math names stay in code and docs. | Review of every screen and report. |
| 13 | **Local first** | Data stays on the machine. A remote option, when it comes, syncs the same append-only log. | No network calls in the engine or the store. |

## Words

| On screen | In the math | Definition |
|---|---|---|
| Score | θ | 1500 + 173.7 × (θ − average θ). This is the Elo scale: 173.7 = 400 / ln 10. |
| Confidence | P(θ_r > θ_r+1 \| answers) | The chance that the item at rank r really belongs above the item at rank r+1 |
| Could be | 90% rank interval | The 5th to 95th percentile of the item's rank |
| Round | Query | One question shown to a judge |
| Rounds left | Forecast | Median and 10–90% range of the remaining rounds |

Terms used in code and docs: **list** (the set being ranked), **item**, **judge** (a person answering), **round type** (`pair`, `pick`, `rank`), **mode** (Quick, Stable, Exact), **fit**, **planner**, **forecast**.

## Architecture

```text
 judge ──answer──> CLI / TUI ──append──> rounds   (SQLite, source of truth)
                      ^                     │
                      │ next round          │ all rounds
                      │                     v
                   planner <──scores, ranges── fit ──> fits      (derived)
                      │
                      ├──> plans                                 (derived)
                      └──> forecast, in background ──> forecasts (derived)
```

```text
rankify/
  engine/          pure math, no I/O
    model.py       likelihoods: pair (with ties), pick, rank; position bias
    fit.py         best fit by Newton's method; uncertainty from the Hessian
    planner.py     candidate rounds; information gain ÷ expected seconds
    stop.py        Quick / Stable / Exact targets
    forecast.py    rounds-left simulation
    timing.py      per-judge seconds per round type and size
  store/           SQLite schema, migrations, queries; no math
  cli/             Typer commands
  tui/             Textual app
  report/          agent report (Markdown and JSON)
  sim/             simulated judges, baselines, benchmark runner
tests/
```

The engine never touches the database, and the store never does math. Both the CLI and the simulator call the same engine functions.

## Model

Each item `i` has a hidden score `θ_i`. During a round, item `i` sits in a display slot `s`, and its utility is `u_i = θ_i + β_s`. The term `β_s` is the position bias of that slot. It is fitted from the data, and the last slot is fixed at 0.

| Round type | Probability of the answer |
|---|---|
| `pair`, i beats j | `e^u_i / (e^u_i + e^u_j)` (Bradley–Terry) |
| `pair`, "can't decide" | `ν·√(e^u_i·e^u_j) / (e^u_i + e^u_j + ν·√(e^u_i·e^u_j))` (Davidson 1970). `ν` is fitted. |
| `pick`, i is best of set S | `e^u_i / Σ_{j∈S} e^u_j` (Luce) |
| `rank`, full order of S | Product of `pick` probabilities: best of all, then best of the rest, and so on (Plackett–Luce) |
| `pick` or `rank`, "can't decide" | Recorded, but carries no information in v1. The planner then prefers pairs for those items. |

**Prior.** Each score starts as `θ_i ~ Normal(0, σ²)`. This gives the fit a single answer, and it keeps items with few rounds near the middle with a wide range. New items can join at any time. `σ` is learned from the judge's own consistency, so a very consistent judge gets a wider `σ` and each answer counts for more.

**Known limits.** The model assumes one score per item (one axis of taste). It also assumes that adding a third option doesn't change the odds between two others. Similar items can break that second assumption, so the planner keeps confident ties out of `pick` rounds.

## Fit

- We find the best fit (maximum a posteriori) by Newton's method. The log posterior is concave in the scores, so there is exactly one best fit.
- Each fit starts from the previous scores. After one new round, it usually needs 1–3 Newton steps.
- Uncertainty comes from the Laplace approximation: the covariance is the inverse of the negative Hessian at the best fit, computed with a Cholesky solve.
- Derived numbers:
  - **Confidence** = `Φ((μ_r − μ_r+1) / sd(θ_r − θ_r+1))` under the normal approximation.
  - **Could be** = the 5th to 95th percentile of the item's rank over 1,000 draws from the approximate posterior.
  - **Confident tie**: `P(|θ_i − θ_j| < m) ≥ 0.9`, where the tie margin `m` defaults to 30 Score points (about a 54% win chance). It is shown as `=`.

## Planner

For each round:

1. Find the items that matter for the mode. For example, Stable uses the top K plus any item whose Could be range overlaps the top K.
2. Build candidates. Start from the pairs among those items whose Could be ranges overlap most, then extend the best pairs greedily to sets of 3, 4 and 5.
3. For each candidate set and each round type, compute the expected information gain (BALD): `H[E_θ p(y|θ)] − E_θ H[p(y|θ)]`. This uses 256 posterior draws, over every possible answer `y`: 2 for a pair (3 with "can't decide"), k for `pick`, k! for `rank`.
4. Divide the gain by the expected seconds for that round type and size.
5. Pick the highest value. Ties are broken with the round's seed, and the display order is shuffled with the same seed.
6. If the best gain is below the floor, stop: nothing left is worth asking.
7. Store the top candidates, with their gain, seconds and value, in `plans`.

Rules:

- A `rank` round has at most 5 items (120 possible answers). The maximum can be configured.
- Confident ties never go into a `pick` round.
- In v1, information gain only counts the items that matter for the mode, because candidates are limited to those items. Weighting the gain by goal is a later refinement.

**Timing model.** For each judge, round type and size, we keep the median seconds over the last 20 answers. Until a judge has answers, defaults apply: `pair` 3 s, `pick` of 4: 5 s, `rank` 3: 6 s, `rank` 4: 9 s, `rank` 5: 13 s. These defaults are guesses until the pilot measures real ones.

## Modes

| Mode | Gives you | Stops when (defaults, adjustable) |
|---|---|---|
| Quick | The winner and top 3, the rest in rough tiers | Confidence ≥ 90% for #1 over #2, and ≥ 80% for #2 over #3 and #3 over #4 |
| Stable | Exact top K, the rest in tiers | Confidence ≥ 90% for every neighbour pair in the top K (K = max(3, ⌈N/4⌉)), and ≥ 90% at each tier boundary below |
| Exact | Every position | Confidence ≥ 95% for every neighbour pair, or a confident tie |

In every mode, the session also stops when the planner finds nothing worth asking. The tiers below the top K are split at the gaps with the highest neighbour Confidence. There are 3 tiers by default.

## Forecast (rounds left)

1. Draw 200 score vectors from the current posterior. Treat each one as the truth.
2. For each, simulate the judge's answers with the fitted model, including ties and position bias. Run a cheap version of the planner (fewer candidates, one Newton step per round) until the stop rule fires.
3. Report the median and the 10–90% range of rounds and of seconds.

The 200 simulations run as one numpy batch in a background thread. The screen shows the previous forecast until the new one is ready.

## Storage

One SQLite file per user, in WAL mode, with STRICT tables and foreign keys on.

**Source of truth**

| Table | Columns |
|---|---|
| `lists` | `id`, `slug`, `title`, `settings` (mode, thresholds), `created_at` |
| `items` | `id`, `list_id`, `name`, `note`, `attributes` (JSON), `added_at`, `removed_at` |
| `judges` | `id`, `name`, `created_at` |
| `rounds` | `id`, `list_id`, `judge_id`, `seq`, `kind`, `shown` (item ids in display order), `answer`, `outcome` (`answered`, `cant_decide`, `undo`), `undoes` (round id), `ms`, `seed`, `engine_version`, `created_at` |

**Derived (can be rebuilt)**

| Table | Columns |
|---|---|
| `fits` | `id`, `list_id`, `upto_round_id`, `engine_version`, `iterations`, `ms`, `created_at` |
| `fit_items` | `fit_id`, `item_id`, `score`, `sd`, `rank`, `rank_lo`, `rank_hi`, `confidence` |
| `fit_state` | `list_id`, latest covariance and prior settings (one row per list, overwritten) |
| `plans` | `round_id`, `candidates` (JSON: items, kind, gain, seconds, value), `chosen` |
| `forecasts` | `fit_id`, `mode`, `rounds_p10`, `rounds_p50`, `rounds_p90`, `seconds_p50`, `ms` |
| `logs` | `ts`, `level`, `event`, `data` (JSON) |

- An undo is a new round with `outcome = undo` that points at the round it cancels. The fit skips cancelled rounds.
- A removed item is hidden from the ranking, but its rounds stay in the fit, because they still tell us about the other items.
- Every derived row records the engine version and the last round it used.

## CLI

```sh
rankify new <list> "<title>" [--items file.txt]
rankify add <list> "<item>" [--note "..."]
rankify play <list> [--mode quick|stable|exact]   # terminal UI
rankify next <list> [--json]                      # show the next round
rankify answer <list> <order...> | --cant-decide  # answer it
rankify undo <list>
rankify show <list> [--json]
rankify why <list> --round <n> [--json]
rankify report <list> [--format md|json]
rankify verify <list>
rankify sim [options]                             # see EXPERIMENT.md
```

`next` and `answer` are the testing hook. The terminal UI, the simulator, the tests and an AI agent all drive the same path.

## Agent report

The report comes in Markdown and JSON, and contains:

- the ranking with Score, Confidence and Could be
- confident ties
- weak spots: neighbour pairs never compared directly, and low Confidence
- slow decisions: the slowest 10% of rounds, which mark close calls
- upsets: answers the model found unlikely (below 20%), and contradiction loops
- position bias and judge consistency
- session stats: rounds, seconds, and whether the mode's target was reached
- with several judges: where they disagree most

An agent can also query the SQLite file directly.

## Performance budget

| Step | Target (95th percentile, up to 200 items) |
|---|---|
| Save answer | < 5 ms |
| Refit | < 10 ms |
| Plan next round | < 30 ms |
| Answer → next round, total | < 50 ms |
| Forecast, in background | < 1 s |

These are targets, not measurements. Performance tests enforce them.

## References

- Bradley, R. A. & Terry, M. E. (1952). Rank analysis of incomplete block designs. *Biometrika*.
- Luce, R. D. (1959). *Individual Choice Behavior*.
- Plackett, R. L. (1975). The analysis of permutations. *Applied Statistics*.
- Davidson, R. R. (1970). On extending the Bradley–Terry model to accommodate ties. *JASA*.
- Houlsby, N. et al. (2011). [Bayesian active learning for classification and preference learning](https://arxiv.org/abs/1112.5745).
- Saha, A. & Gopalan, A. (2019). [Active ranking with subset-wise preferences](https://arxiv.org/abs/1810.10321).
- Maystre, L. & Grossglauser, M. (2017). [Just sort it! A simple and effective approach to active preference learning](https://proceedings.mlr.press/v70/maystre17a.html).
