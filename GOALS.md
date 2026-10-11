# Goals

Each goal has a measure and a target. The targets are our starting proposal. We may change them after the first benchmark, but every change must be written down here, with the reason, before the benchmark that checks it runs (see [EXPERIMENT.md](EXPERIMENT.md)).

## Speed

**G1. Faster than Elo.** For 20 items and a judge of normal consistency, reaching the Stable target takes at most a third of the simulated time that Elo with random pairs needs for the same accuracy.

**G2. Faster than the strong baseline.** Reaching each mode's target takes at least 20% less simulated time than Just Sort It. If we can't manage that, we use Just Sort It's way of picking questions.

**G3. Mixed rounds pay off.** Using all round types (pair, pick, rank) takes less time than using pairs only. This must hold under the default timing model and under the timing model measured in the pilot.

**G4. Instant.** For lists of up to 200 items, the time from answer to next round is under 50 ms at the 95th percentile. The forecast finishes within 1 second, in the background.

## Honesty

**G5. Confidence is calibrated.** When Confidence says c%, the order is really right about c% of the time, within 5 points on average (expected calibration error ≤ 0.05).

**G6. Could be is honest.** The 90% range contains the true rank 85–95% of the time.

**G7. Rounds left is honest.** The 10–90% range contains the actual number of rounds left 70–90% of the time, and the median is off by no more than 25%.

**G8. Modes deliver what they promise.** At the moment each mode stops:

- Quick: the true #1 is at #1 in at least 90% of runs.
- Stable: at least 90% of neighbour pairs in the top part are in the right order.
- Exact: at least 95% of neighbour pairs are in the right order, not counting true near-ties.

## Correctness

**G9. Reproducible.** Shuffling the answer log and refitting leaves every score unchanged, within 1e-9. `rankify verify` passes on every stored list.

**G10. Correct math.** On the same data with the same prior, our scores match those from the `choix` library within 1e-4.

## Reach

**G11. Ready for agents.** Every command that prints results supports `--json`, and the report covers everything listed in [DESIGN.md](DESIGN.md#agent-report).

**G12. Ready for many judges.** Merging two judges' logs gives the same result in any order. A judge with ten times the votes doesn't dominate the shared ranking.

## Not now

These are deliberately out of scope for now:

- a browser UI
- a remote or public server, accounts, and protection against fake votes
- a mobile app
- recommending items you haven't tried
- taste with more than one axis (v1 assumes one score per item, and reports answers it can't explain)
- publishing to PyPI (the name `rankify` is taken there, so we'll pick a package name later)
