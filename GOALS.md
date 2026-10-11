# Goals

Each goal has a measure and a target. The targets are our starting proposal. We may adjust them after the first benchmark, but every change must be written down here, with the reason, before the benchmark that checks it runs (see [EXPERIMENT.md](EXPERIMENT.md)).

## Goals

| # | Goal | Measure | Target |
|---|---|---|---|
| G1 | **Faster than Elo** | Simulated seconds to reach the Stable target, compared with Elo on random pairs reaching the same accuracy. Measured with 20 items and a judge with normal consistency. | At most one third of Elo's time |
| G2 | **Beat the strong baseline** | Simulated seconds to reach each mode's target, compared with Just Sort It | At least 20% less time. If we can't beat it, we use Just Sort It as the planner. |
| G3 | **Mixed rounds pay off** | Seconds to target with all round types, compared with pairs only | Less time with all round types, under both the default and the measured timing models |
| G4 | **Calibrated Confidence** | When Confidence says c%, how often the order is really right | Within 5 points of c on average (expected calibration error ≤ 0.05) |
| G5 | **Honest Could be** | How often the 90% range contains the true rank | 85–95% of the time |
| G6 | **Honest rounds left** | How often the 10–90% forecast range contains the actual rounds left | 70–90% of the time, with median error ≤ 25% |
| G7 | **Instant** | Time from answer to next round, up to 200 items | 95th percentile < 50 ms. Forecast < 1 s, in the background. |
| G8 | **Reproducible** | Refit after shuffling the rounds, and `rankify verify` on every stored list | Scores equal within 1e-9. `verify` passes. |
| G9 | **Correct math** | Our fits compared with `choix` on the same data and the same prior | Scores equal within 1e-4 |
| G10 | **Precision modes** | Accuracy at the moment each mode stops | Quick: true #1 is at #1 in ≥ 90% of runs. Stable: neighbour order right for ≥ 90% of pairs in the top K. Exact: neighbour order right for ≥ 95% of pairs that aren't true near-ties. |
| G11 | **Ready for agents** | Every read command supports `--json`. The report covers everything listed in [DESIGN.md](DESIGN.md#agent-report). | All read commands and report sections present |
| G12 | **Ready for many judges** | Data model, order-independent fit, and equal judge weight | Merging two judges' logs gives the same result in any order. One judge with 10× the votes doesn't dominate the consensus. |

## Non-goals (for now)

- A browser UI.
- A remote or public server, accounts, and protection against fake votes.
- A mobile app.
- Recommending items you haven't tried.
- Taste with more than one axis. v1 assumes one score per item and reports answers it can't explain.
- Publishing to PyPI. The name `rankify` is taken there, so we'll pick a package name later.
