# Proposal

## The problem

We want to rank lists, for example:

- places we want to travel to
- products we really want to buy
- restaurants we tried this month
- later, shared lists that many people vote on, like "best NBA player of all time"

Ranking a whole list by hand is hard. Early placements anchor later ones, a long list is more than a person can hold in mind at once, and nobody can reproduce how the final order came about.

Elo-style voting ("A or B?", many times) fixes part of that. Each judgment is small and separate, and math combines them into a ranking. The idea is sound, but in practice it has these problems.

**Slow, undirected matching.** Pairs are chosen at random. Most have predictable answers, the same pair can come up again when nothing about it is in doubt, and a match like #1 against #40 carries almost no information.

**Slow to settle.** An order is only certain once every neighbouring pair (#1 vs #2, #2 vs #3, and so on) has been compared directly. Random pairs find those only by chance. For 20 items, random pairs need about 181 of the 190 possible pairs before the order is certain. A good sort needs 62.

**Order dependence.** Elo updates one match at a time, so the same matches in a different order give different scores. With many voters, the first few can count more than those who come later.

**No progress signal.** There is no estimate of how many rounds remain.

**Pairs only.** Three close items can't be ordered in one step, even when that would be faster.

## What we want

- **Decisive rounds.** Every question is one the system can't already predict, and its answer changes the ranking where it matters.
- **Flexible rounds.** A round can be a pair, "pick the best of A B C D", or "put these in order". The math decides which, round by round, and only when it helps.
- **A statistical model.** Separate judgments, robust to a careless answer, and reproducible.
- **Adjustable precision.** Quick, Stable and Exact modes, each defined as a confidence target.
- **Rounds left.** An honest estimate of the rounds remaining, with a range.
- **Instant.** The next round appears with no visible wait.
- **Many judges, treated fairly.** Votes count the same no matter when they were cast. A shared ranking and each person's own ranking come from the same data.
- **Local data.** All data, intermediate steps and logs live in a local SQLite file.
- **A report for an AI agent** covering close calls, contradictions and patterns.
- **CLI and terminal UI first.** They are the easiest to test and script. A browser UI can come later.
- **Plain words on screen**: Score, Confidence, Could be. Math names stay in the code and docs.

## What we don't want

- Slow convergence.
- Random matching.
- Asking every possible pair.
- Matches that can't change anything.
- A plain sort that treats every answer as final, where one wrong answer misplaces an item permanently.
- Scores that depend on the order of votes, or early voters who count more.
- Fake precision: exact-looking numbers without ranges, or a rounds-left count that pretends to be exact.
- Math jargon on screen.

## Proposed approach

Every item has a hidden score. One statistical model links the scores to the judge's answers: Bradley–Terry for pairs, and Plackett–Luce for "pick the best" and "put in order". After every round, the model is fitted to all answers at once. That gives each item a score and an uncertainty range. A planner then picks the next round, meaning both the items and the round type, by how much information it expects per second of the judge's time. Each mode stops when its confidence target is met. The rounds-left estimate comes from simulating the rest of the session many times. All answers go into a log in SQLite that is only ever added to, and everything else is derived from it.

The rules behind this are in [PHILOSOPHY.md](PHILOSOPHY.md), and the details are in [DESIGN.md](DESIGN.md).

### Why not plain Elo

Elo uses the same win-probability curve as Bradley–Terry. An Elo update is one small step toward the Bradley–Terry fit. Fitting all answers at once is Elo carried to the end over the full history, and that removes the order dependence. Elo also picks matches without looking at what is still uncertain, which is where most of its rounds are wasted.

### Why not a plain sort

With a perfectly consistent judge, a sort needs close to the minimum number of comparisons. People are not perfectly consistent. A sort treats each answer as final, so one mistake stays forever, and it has no notion of confidence. We keep the sort's efficiency as a benchmark to beat ("Just Sort It", below), but not its rigidity.

## Prior art

The core model comes from Bradley & Terry (1952), Luce (1959) and Plackett (1975). These link hidden scores to pair, pick and ranking answers. Davidson (1970) adds ties, which we use for "can't decide". Elo gives us the familiar Score scale. Glicko (Glickman 1999) and TrueSkill (Herbrich, Minka & Graepel 2006) showed the value of giving every rating a range.

[Chatbot Arena](https://lmsys.org/blog/2023-12-07-leaderboard) moved from online Elo to a Bradley–Terry fit in 2023, citing more stable ratings. That is a precedent for fitting all votes at once.

The planner builds on [BALD](https://arxiv.org/abs/1112.5745) (Houlsby et al. 2011), which chooses questions by expected information gain. [Saha & Gopalan (2019)](https://arxiv.org/abs/1810.10321) tell us when multi-item rounds are worth it. Under noise, "pick the best" is no faster than pairs, while ranking the top m items is about m times faster.

[Just Sort It](https://proceedings.mlr.press/v70/maystre17a.html) (Maystre & Grossglauser 2017) re-runs quicksort as a question-picking strategy under Bradley–Terry. It is cheap and strong, so it is the main baseline we must beat. [openskill](https://www.npmjs.com/package/openskill) (Weng & Lin 2011) gives online Plackett–Luce ratings and serves as another baseline. It updates one match at a time, so it is order-dependent.

For checking our math, [choix](https://pypi.org/project/choix/) is a Python library for Bradley–Terry and Plackett–Luce fits. [corsort](https://pypi.org/project/corsort) studies sorts that give a useful result when stopped early, which is relevant to Quick mode. Pairwise "sorter" pages like charasort show the demand, but they ask in pairs only and give no confidence. We know charasort from training data and haven't re-checked it.

## What may be new

These parts combine known methods in a way we have not seen in a tool. We have not done a literature review, so we do not claim they are new.

1. One planner that picks among round types (pair, pick, and ordering 3 to 5 items) by information gained per second of the judge's measured time.
2. A rounds-left estimate made by simulating the planner itself on the current fit.
3. A personal ranking that starts from a shared ranking, so the planner only asks where the judge is likely to disagree with the crowd.

## Risks and open questions

- **Time costs are guessed.** The planner trades information against seconds, but how long each round type takes is a guess for now. A pilot with real lists will measure it.
- **Taste may not lie on one axis.** The model gives each item one score. Travel picks might follow two axes, such as relaxing against exciting. v1 reports answers the model can't explain. A two-axis model is out of scope.
- **Similar items split votes.** Two near-identical items in a "pick the best" round can both lose to a different third item. The planner keeps near-duplicates out of pick rounds, and the benchmark includes a judge with this bias.
- **The planner may not beat Just Sort It.** If it doesn't, the planner adds complexity for nothing, and we use Just Sort It instead. [ROADMAP.md](ROADMAP.md) has the check.
- **Public rankings need accounts and abuse protection.** Math can't stop fake votes. This is out of scope until local use works.
- **The PyPI name `rankify` is taken** by an unrelated toolkit. The command can still be `rankify`, but the package name is still to be decided.
