# Session-length scripts and logs

The scripts behind [the session-length report](../2026-10-15-session-length.md). Like step 4's, they are one-off analyses that set rankify's switches (`service.EP_FIT`, `planner.ASK_AGAIN`) directly, and they use practice lists only (seeds 70000 + 1000 × items + list number), never the benchmark's test lists.

| File | What it is |
|---|---|
| `length_eval.py` | runs every setting, judge, mode and list through `bench.run_one` and prints one JSON line per session: rounds until each target is reached, rounds at the stop, right at the stop, share of repeats, and the ranking's quality after 10, 20, 30, 40 and 60 answers |
| `summarize.py` | turns those lines into the report's tables |
| `n20.log`, `n10.log` | `summarize.py`'s output for 20 and 10 items |

Run from the repository root:

```sh
uv run python experiments/2026-10-15-session-length/length_eval.py . laplace-always,laplace-contradicted,laplace-once,ep-always,ep-contradicted,ep-once perfect,normal,careless,human,noisy 20 quick,stable 20 4 > n20.jsonl
uv run python experiments/2026-10-15-session-length/summarize.py n20.jsonl > experiments/2026-10-15-session-length/n20.log
```

The arguments are the repository root, the settings (`<fit>-<rule>`), judges, items, modes, lists, worker processes and, optionally, the first list number. The JSON lines (about 0.7 MB per size) aren't kept; the seeds are fixed, so the command reproduces them.
