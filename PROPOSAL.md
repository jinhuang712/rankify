# Proposal

## The problem

We want to rank lists, for example:

- places we want to travel to
- products we really want to buy
- restaurants we tried this month
- later, shared lists that many people vote on, like "best NBA player of all time"

Ranking a whole list by hand is hard. You anchor on the first items you place, small lists are fine but long ones are not, and nobody else can reproduce how you got there.

Elo-style voting ("A or B?", many times) fixes part of that. Each judgment is small and separate, and math combines them into a ranking. We like that idea. In practice it has these problems:

| Pain point | What happens |
|---|---|
| Slow | Many rounds are needed before the order is useful. |
| Random matching | Pairs are chosen at random, with no direction. Most of them have answers that are already predictable. |
| Repeats | The same pair can come up again even when nothing about it is in doubt. |
| Low-value matches | #1 against #40 tells you almost nothing. |
| Slow to settle | An order is only certain once every neighbouring pair (#1 vs #2, #2 vs #3, and so on) has been compared. Random pairs only find those by luck. For 20 items, random pairs need about 181 of the 190 possible pairs. A good sort needs 62. |
| Order dependence | Elo updates one match at a time, so the same matches in a different order give different scores. With many voters, the first few can count more than the rest. |
| No progress | You can't tell how many more rounds are needed. |
| Pairs only | You can't say "these three are close, let me just order them", even when that would be faster. |

## What we want

- **Decisive rounds.** Every question is one the system cannot already predict, and whose answer changes the ranking where it matters.
- **Flexible rounds.** A round can be a pair, "pick the best of A B C D", or "put these in order". The math decides which, round by round, only when it helps.
- **Real math.** Separate judgments, robust to a careless answer, and reproducible. Not hand ranking with extra steps.
- **Adjustable precision.** Quick, Stable and Exact modes, each defined as a confidence target.
- **Rounds left.** An honest estimate of how many rounds remain, with a range.
- **Instant.** The next round appears with no visible wait.
- **Many judges, fairly.** Votes count the same no matter when they were cast. A shared ranking and each person's own ranking come from the same data.
- **Local data.** All data, intermediate steps and logs live in a local SQLite file.
- **A report for an AI agent**, so it can dig into close calls, contradictions and patterns.
- **CLI and terminal UI first.** They are the easiest to test and script. A browser UI can come later.
- **Plain words in the UI**: Score, Confidence, Could be. Math names stay in the code and docs.

## What we don't want

- Slow convergence.
- Random matching.
- Asking every possible pair.
- Matches that can't change anything.
- A plain sort that treats every answer as final. One careless click would then misplace an item for good.
- Scores that depend on the order of votes, or early voters that count more.
- Fake precision: exact-looking numbers without ranges, or a rounds-left count that pretends to be exact.
- Math jargon on screen.

## Proposed approach

In one paragraph: every item has a hidden score. One statistical model, Bradley–Terry for pairs and Plackett–Luce for "pick the best" and "put in order", links scores to answers. After every round, the model is fitted to all answers at once, which gives each item a score and an uncertainty range. A planner then picks the next round, the items and the round type, by how much information it expects per second of the judge's time. Each mode stops when its confidence target is met. The rounds-left estimate comes from simulating the rest of the session many times. All answers go into an append-only table in SQLite, and everything else is derived from it.

The details are in [DESIGN.md](DESIGN.md).

### Why not plain Elo

Elo uses the same win-probability curve as Bradley–Terry. An Elo update is one small step toward the Bradley–Terry fit. Fitting all answers at once is Elo carried to the end over the full history, which removes the order dependence. Elo also picks matches without looking at what is still uncertain, which is where most of its rounds are wasted.

### Why not a plain sort

A sort with a perfectly consistent judge needs close to the minimum number of comparisons. People are not perfectly consistent. A sort treats each answer as final, so one mistake stays forever, and it has no notion of confidence. We keep the sort's efficiency as a benchmark ("Just Sort It", below) but not its rigidity.

## Prior art

| Work | What it is | What we take from it |
|---|---|---|
| Bradley & Terry (1952), Luce (1959), Plackett (1975) | Models that link hidden scores to pair, pick-best and ranking answers | The core model |
| Elo | Online rating with the logistic curve | The Score scale (1500 average) |
| Davidson (1970) | Bradley–Terry with ties | "Can't decide" answers |
| Glicko (Glickman 1999), TrueSkill (Herbrich, Minka, Graepel 2006) | Ratings with uncertainty | Every score has a range |
| [Chatbot Arena (2023)](https://lmsys.org/blog/2023-12-07-leaderboard) | Moved from online Elo to a Bradley–Terry fit for more stable ratings | Precedent for fitting all votes at once |
| [BALD, Houlsby et al. (2011)](https://arxiv.org/abs/1112.5745) | Choosing questions by expected information gain | The planner's scoring rule |
| [Saha & Gopalan (2019)](https://arxiv.org/abs/1810.10321) | Active ranking with subsets: "pick the best" is no faster than pairs under noise, while ranking the top m is about m times faster | When multi-item rounds are worth it |
| [Just Sort It, Maystre & Grossglauser (2017)](https://proceedings.mlr.press/v70/maystre17a.html) | Re-running quicksort as an active strategy under Bradley–Terry | Main baseline to beat |
| [openskill](https://www.npmjs.com/package/openskill) (Weng & Lin 2011) | Online Bayesian ratings with Plackett–Luce | Baseline. It updates one match at a time, so it is order-dependent. |
| [choix](https://pypi.org/project/choix/) | Python library for Bradley–Terry and Plackett–Luce fits | Reference to check our fits against |
| [corsort](https://pypi.org/project/corsort) | Research on sorts that give a useful result if stopped early | Reference for Quick mode |
| charasort | Pairwise merge-sort "sorter" web page | Shows demand. Pairs only, no confidence. (Known from training data, not re-checked.) |

## What may be new

These parts combine known methods in a way we have not seen in a tool. We have not done a literature review, so we do not claim they are new.

1. One planner that picks among round types (pair, pick best, rank 3 to 5) by information gained per second of the judge's measured time.
2. A rounds-left estimate made by simulating the planner itself on the current fit.
3. A personal ranking that starts from a shared ranking, so the planner only asks where you are likely to disagree with the crowd.

## Risks and open questions

| Risk or question | Why it matters | Plan |
|---|---|---|
| The time cost of each round type is guessed | The planner trades information against seconds | Measure it in a pilot with real lists, then replace the guesses |
| Taste may not lie on one axis | The model assumes one score per item. Travel picks may follow two axes, such as relaxing vs exciting. | Report answers the model can't explain. A two-axis model is out of scope for v1. |
| Similar items split votes | Two near-identical items in a "pick the best" round can both lose to a different third item | Keep near-duplicates out of pick-best rounds. Test with a simulated judge that has this bias. |
| The planner may not beat Just Sort It | Then the planner adds complexity for nothing | Decision gate in [ROADMAP.md](ROADMAP.md). If it doesn't beat Just Sort It, we use Just Sort It as the planner. |
| Public rankings need accounts and abuse protection | Math can't stop fake votes | Out of scope until local use works |
| The PyPI name `rankify` is taken by an unrelated toolkit | We can't publish under that name | The command can still be `rankify`. The package name is to be decided. |
| License | The repo is public | To be decided |
