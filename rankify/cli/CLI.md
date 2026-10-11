# rankify CLI

> **Partly built.** Working now: `new` (with `--method`), `add`, `remove`, `lists`, `next` (random pairs for rankify), `answer`, `undo`, `show`, `verify` and `bench`. Everything else here is planned. Exit code 3 is used by methods that finish, such as `insertion-sort`. `next --json` returns `"rounds_left": null` and `show --json` returns `"target_reached": null` until the forecast and the stopping rules exist.

The CLI is the main way to use rankify, and also the way rankify is tested. The terminal UI, the simulator, the test suite and AI agents all drive the same commands.

## Basics

- A list is named by a short slug, like `nba` or `travel`.
- All data lives in one SQLite file, `~/.rankify/rankify.db` by default. To use another file, pass `--db PATH` or set `RANKIFY_DB`.
- You answer as the judge `me` unless you pass `--judge NAME`.
- Every command that prints results accepts `--json`, for scripts and agents.

## Make a list

```sh
rankify new travel "Places I want to go"
rankify new nba "Best NBA player ever" --items players.txt   # one item per line
rankify add travel "Kyoto" --note "autumn leaves"
rankify remove travel "Paris"     # hidden from the ranking; its rounds still count
rankify lists                     # all lists and their progress
```

## Rank in the terminal UI

```sh
rankify play travel               # uses the list's mode, Stable by default
rankify play travel --mode quick
```

```text
 Best NBA player ever                  Stable · ~14 rounds left (10–19)
 ──────────────────────────────────────────────────────────────────────
 Round 23 · Put these in order, best first

   1  Michael Jordan
   2  LeBron James
   3  Kareem Abdul-Jabbar

 > 2 1 3                    [t] can't decide   [u] undo   [r] ranking
```

To answer, type the numbers in order, best first, and press Enter. For a pair or a pick, one number is enough. You can also move items with ↑, ↓ and Space, then press Enter.

The other keys:

- `t`: can't decide
- `u`: undo the last answer
- `r`: show the current ranking (hidden by default, so it doesn't sway you)
- `q`: quit

Progress is saved after every answer.

## Rank one round at a time

```sh
rankify next travel               # show the next round
rankify answer travel 2 1 3       # numbers as shown, best first
rankify answer travel --cant-decide
rankify undo travel
```

`next` keeps showing the same round until it is answered. Scripts should pass the round number back, so an answer can't land on the wrong round:

```sh
rankify next travel --json
rankify answer travel --round 23 2 1 3
```

## See results

```sh
rankify show travel               # Score, Confidence, Could be
rankify show travel --tiers       # grouped into tiers
rankify why travel --round 17     # why that round was asked
rankify report travel --format md # report for an AI agent; md or json
```

## Manage data

```sh
rankify export travel > travel.jsonl              # the answer log, one round per line
rankify import travel friend.jsonl --judge alex   # merge another judge's log (Phase 6)
rankify verify travel             # rebuild everything from the log and compare
rankify rebuild travel            # rebuild derived data after an engine upgrade
```

## Benchmark

```sh
rankify bench --items 10,20 --runs 20 --report experiments/2026-10-12-human-judge.md
rankify bench --judges human,perfect,noisy --methods rankify,elo,glicko2
rankify new demo "Demo" --items items.txt --method trueskill   # run any method by hand
```

`bench` draws hidden scores and runs every method through these same commands. A simulated judge answers each round, and the default is one that behaves like a person.

`--method` picks the ranking method for a list. `rankify` is the default. The others are baselines to compare against:

- Rating systems: `elo`, `elo-close`, `glicko2`, `trueskill`, `openskill` and `arena`.
- Reference sorts: `just-sort-it` and `insertion-sort`.

Glicko-2, TrueSkill and openskill need the development dependencies (`uv sync`). The benchmark is described in [EXPERIMENT.md](../../EXPERIMENT.md).

## JSON output

The JSON output uses the same plain words as the screen.

`rankify next nba --json`:

```json
{
  "list": "nba",
  "round": 23,
  "kind": "rank",
  "items": [
    {"n": 1, "id": "jordan", "name": "Michael Jordan"},
    {"n": 2, "id": "lebron", "name": "LeBron James"},
    {"n": 3, "id": "kareem", "name": "Kareem Abdul-Jabbar"}
  ],
  "rounds_left": {"median": 14, "low": 10, "high": 19, "updating": false}
}
```

`rankify show nba --json`:

```json
{
  "list": "nba",
  "mode": "stable",
  "target_reached": false,
  "items": [
    {"rank": 1, "id": "jordan", "name": "Michael Jordan",
     "score": 1712, "confidence": 0.74, "could_be": [1, 2]},
    {"rank": 2, "id": "lebron", "name": "LeBron James",
     "score": 1690, "confidence": 0.81, "could_be": [1, 3]}
  ]
}
```

## Exit codes

- `0`: success
- `1`: error
- `2`: bad usage
- `3`: nothing left to ask, because the mode's target is reached

## Driving rankify from a script

This loop runs until `next` exits with a non-zero code, either `3` (done) or an error:

```sh
while rankify next travel --json > round.json; do
  # decide here, then:
  rankify answer travel --round "$(jq .round round.json)" 1
done
```
