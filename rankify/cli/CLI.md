# rankify CLI

> **Mostly built.** Working now:
>
> - `new` (with `--method`, `--rounds` and `--calibrate`), `add`, `remove` and `lists`
> - `next`: the rankify planner, with `--mode` to override the list's mode and an estimate of rounds left. It asks pairs, or with `new --rounds mixed` also picks and orderings of 3 to 5 items
> - `answer`, `undo`, and `play`, the terminal UI
> - `show` (with `--tiers`), `why`, `forecast` and `report`
> - `export`, `verify`, `rebuild`, `bench` and `calibrate`
>
> Still planned: `import`, which comes with several judges in Phase 6. `next` exits with code 3 when the mode's target is reached or nothing is left worth asking. Every command that prints results takes `--json`.

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

A list asks pairs ("which is better?") unless it is made with `--rounds mixed`. A mixed list also asks picks ("which is best?") and orderings ("put these in order, best first") of 3 to 5 items, whichever teaches the most per second of your time. In the Phase 3 benchmark mixed rounds were faster for some targets and slower for others, so they are not the default yet (see [ROADMAP.md](../../ROADMAP.md#phase-3-mixed-rounds)).

## Rank in the terminal UI

```sh
rankify play travel               # until the mode's target, or until you press q
rankify play travel --mode quick  # this session in another mode
rankify play travel --rounds 20   # stop after 20 answers
```

```text
 Best NBA player ever · Stable · ~14 rounds left (10–19) · 22 answered

 Round 23 · Put these in order, best first

 > 1  Michael Jordan
   2  LeBron James
   3  Kareem Abdul-Jabbar

 > 2 1
 Type the numbers best first, or arrange with ↑ ↓ and Space, then Enter.
```

For a pair or a pick, press the item's number. For an ordering, type the numbers best first: the last one fills itself in, and Backspace takes back a key. You can also arrange the items: ↑ and ↓ move the cursor, Space picks up the item under it (then ↑ and ↓ move the item), Space puts it down, and Enter answers.

The other keys:

- `t`: can't decide
- `u`: undo the last answer
- `r`: show or hide the current ranking (hidden by default, so it doesn't sway you)
- `q`: quit

Each answer is timed from when the round appears to the last key, and saved at once. Rounds left are worked out between keypresses, so the next round never waits for them. Until the new estimate is ready, the header shows the last one, marked "updating".

When input or output isn't a terminal, `play` reads keys line by line instead (`--plain` forces this).

## Rank one round at a time

```sh
rankify next travel               # show the next round
rankify answer travel 2 1 3       # numbers as shown, best first
rankify answer travel 213         # the same, typed as one number
rankify answer travel 2 1         # the same: the last one is implied
rankify answer travel --cant-decide
rankify undo travel
```

`next` keeps showing the same round until it is answered. Scripts should pass the round number back, so an answer can't land on the wrong round:

```sh
rankify next travel --json
rankify answer travel --round 23 2 1 3
```

For a pair or a pick, give one number: the better or the best item. For an ordering, give every number best first, or all but the last. "Can't decide" on a pair counts as a tie. On a pick or an ordering it is recorded but teaches nothing, and that set isn't asked again.

`next --mode exact` asks this session in another mode without changing the list. A script that measures answer times itself can pass them with `answer --ms 2400`. The benchmark does this, so the planner learns the judge's pace.

## See results

```sh
rankify show travel               # Score, Confidence, Could be
rankify show travel --tiers       # grouped into tiers whose order is settled
rankify why travel --round 17     # why that round was asked
rankify forecast travel           # rounds left, in the list's mode
rankify report travel             # report for an AI agent, in Markdown
rankify report travel --format json
```

`forecast` works out how many answers each pair the mode still needs will take, over 64 draws of what the true scores might be, and gives the median and the 10–90% range of the rounds left (see [DESIGN.md](../../DESIGN.md#rounds-left)). It allows for your habits: how often you say "can't decide", how you tire as a sitting goes on, and how decisive your answers have been so far. On a mixed list it counts a pick or ordering as about 2.5 pairs. `forecast` and `report` take `--judge` like `next`, since habits are each judge's own. It takes a few milliseconds, and a forecast is saved and reused until the list changes. `next` shows the same estimate; `next --no-forecast` skips it. When too many draws would need more than 50 rounds per item, the answer is "at least N rounds". With `--json` it also gives `draws` and `ms`.

`show --tiers` starts a new tier wherever the item above is confidently better (Confidence of at least 90%, as Stable mode asks of its tiers). Inside a tier the order isn't settled yet. `--json` adds a `tier` number to each item. Methods without Confidence, like Elo, have no tiers.

`report` gives an agent what it needs to dig deeper: the ranking with Score, Confidence and Could be; confident ties; weak spots (close neighbours never compared directly); slow decisions; upsets the final scores can't explain; the judge's position bias and consistency; and with several judges, where they disagree.

`why` lists the rounds the planner weighed, best first: pairs, picks and orderings. For each it shows the expected bits about the order of the shown items, counting only the pairs that matter for the mode, and the expected answer time. `--json` adds how likely the first item of a pair was to win, and the planner's time guesses for each kind and size of round. It works for rounds the planner chose. Calibration repeats, undos and baseline methods have no plan to show.

## Manage data

```sh
rankify export travel > travel.jsonl              # the list, its items and every round
rankify export travel --out backup/travel.jsonl
rankify import travel friend.jsonl --judge alex   # merge another judge's log (Phase 6)
rankify verify travel             # rebuild the ranking from the log and compare
rankify rebuild travel            # refit with this version of rankify, after an upgrade
```

`export` writes JSON lines: first the list (title and settings), then one line per item, numbered from 1 in the order they were added (removed ones included, with when they were removed), then one line per round, undos and "can't decide" included, with the judge, the answer and its time. Rounds refer to items, and an undo to the round it cancels, by number, so the file stands on its own. Replaying it into an empty database gives the same ranking. Unanswered rounds and the planner's notes are left out; they are derived.

`rebuild` refits the list from its answer log alone with the installed version of rankify, drops the saved forecasts, and lists the items that moved. The fits made after each answer, and the planner's records, stay as they were: they record what rankify believed, and asked, at the time. `show` also refits on its own when the engine changes; `rebuild` is the way to see what changed.

## Benchmark

```sh
rankify bench --items 10,20 --runs 20 --report experiments/2026-10-12-human-judge.md
rankify bench --judges human,perfect,noisy --methods rankify,elo,glicko2
rankify bench --judges sharp,normal,fuzzy,careless,biased,thurstone,similar,tired
rankify bench --methods rankify,rankify-closest,rankify-per-round   # planner variants
rankify bench --methods rankify,rankify-mixed --set-time-scale 0.5 --cache half.jsonl
rankify new demo "Demo" --items items.txt --method trueskill   # run any method by hand
```

`bench` draws hidden scores and runs every method through these same commands. A simulated judge answers each round, and the default is one that behaves like a person. The other judges each change one thing (EXPERIMENT.md, Part 1): `sharp`, `normal` and `fuzzy` answer as the model assumes, telling neighbours apart 90%, 75% and 60% of the time; `careless`, `biased`, `thurstone`, `similar` and `tired` are normal with one twist. Besides the rating systems, `--methods` takes the reference sorts `just-sort-it`, `insertion-sort` and `ford-johnson`, and two planner variants that check rankify's design: `rankify-closest` (the pair closest to 50/50) and `rankify-per-round` (information per round, not per second). They run with `new --planner`, a benchmark-only option.

In `--methods`, `rankify` is rankify as shipped, and `rankify-mixed` is a list made with `--rounds mixed`. Both run once per mode. `--set-time-scale` multiplies how long the judge takes on pick and rank rounds, to test how much a result depends on that guess. `--cache` saves each finished run, so an interrupted benchmark resumes. Use a separate cache for each scale.

`--method` picks the ranking method for a list. `rankify` is the default. The others are baselines to compare against:

- Rating systems: `elo`, `elo-close`, `glicko2`, `trueskill`, `openskill` and `arena`.
- Reference sorts: `just-sort-it` and `insertion-sort`.

Glicko-2, TrueSkill and openskill need the development dependencies (`uv sync`). The benchmark is described in [EXPERIMENT.md](../../EXPERIMENT.md).

## Calibrate the benchmark's human judge

```sh
rankify new calib "Places I want to go" --items places.txt --calibrate
rankify play calib --rounds 150
rankify calibrate calib --out ~/.rankify/judge-me.json
rankify calibrate calib places food --out ~/.rankify/judge-me.json   # several lists
rankify bench --judge-profile ~/.rankify/judge-me.json
```

`--calibrate` makes about 15% of rounds repeat an earlier pair with the sides swapped. That measures how consistent you are. `calibrate` then estimates how you answer and marks each setting as measured or kept as the default guess, depending on how many answers the session has. `bench --judge-profile` uses only the measured settings.

With several lists, the pairs from all of them are pooled, and timed picks and orderings measure how long sets take next to your pace on pairs: real time over the time the benchmark's judge would take, whose median becomes `set_time_scale` once 8 or more are timed. On simulated judges it reads about 10% low, which still tells half, guessed and double time apart. Pairs from ordinary lists were chosen by the planner, which leans toward close calls; the profile notes that the bias corrections assume random pairs. The method is described in [EXPERIMENT.md](../../EXPERIMENT.md#part-2-calibration-and-pilot).

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
  "rounds_left": {"median": 14, "low": 10, "high": 19, "at_least": null, "updating": false}
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
