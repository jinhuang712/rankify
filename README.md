# rankify

Rank anything by answering a few quick questions, with real statistics behind every answer.

> **Status: Phase 4 done.** rankify picks each pair by how much it teaches about the order you care about. It stops when your mode's confidence target is reached or nothing is left worth asking, and `rankify why` explains any question. Against a simulated human judge on 20 items, it reaches the right top 3 in about a quarter of Elo's time. `rankify play` is a terminal UI that shows about how many rounds are left, and `rankify report` writes a report an AI agent can dig into. Lists made with `--rounds mixed` also ask "pick the best" and "put these in order" for 3–5 items. That isn't the default until real answer times are measured (see [ROADMAP.md](ROADMAP.md) and [EXPERIMENT.md](EXPERIMENT.md#results)).

## Try it

```sh
uv sync
uv run rankify new travel "Places I want to go" --items places.txt
uv run rankify play travel        # answer rounds in the terminal UI; q to stop
uv run rankify show travel
uv run rankify report travel      # a report for an AI agent
uv run rankify next travel        # or one round at a time, for scripts:
uv run rankify answer travel 1
uv run rankify bench --runs 5     # compare against Elo and other rating systems
uv run pytest
```

## Why

Ranking a whole list by hand is hard, and the result is hard to trust. Elo-style voting ("A or B?", many times) splits the work into small, separate judgments and lets math combine them. That idea is good, but Elo asks random pairs, repeats itself, and takes a long time to settle. With 20 items, random pairs need about 181 of the 190 possible pairs before the order is certain. A good sort needs 62.

rankify keeps the separate judgments and the math, and cuts the waste:

- Every question is chosen to be decisive: one whose answer rankify can't already predict.
- A round can be a pair, "pick the best of these", or "put these in order" (for now, only with `--rounds mixed`). The math picks whichever tells it the most per second of your time.
- Scores come from one model fitted to all answers at once, so the same answers always give the same result, in any order.
- You choose how sure you need to be (Quick, Stable or Exact), and rankify shows how many rounds are probably left.

## How it will look

```sh
rankify new nba "Best NBA player ever" --items players.txt
rankify play nba --mode stable
rankify show nba
```

```text
 #  Item                  Score  Confidence  Could be
 1  Michael Jordan         1712      74%       #1–#2
 2  LeBron James           1690      81%       #1–#3
 3  Kareem Abdul-Jabbar    1655      62%       #2–#5
```

The numbers above are made up. **Score** uses the Elo scale, with 1500 as the average. **Confidence** is the chance that an item really belongs above the next one. **Could be** is where the item might really rank, as a 90% range.

All commands are in [rankify/cli/CLI.md](rankify/cli/CLI.md).

## Documents

- [PROPOSAL.md](PROPOSAL.md): the pain points, what we want and don't want, and prior work
- [PHILOSOPHY.md](PHILOSOPHY.md): the principles behind the design
- [DESIGN.md](DESIGN.md): how it works and why
- [GOALS.md](GOALS.md): goals, how we measure them, and non-goals
- [EXPERIMENT.md](EXPERIMENT.md): how we benchmark it against Elo and other methods
- [ROADMAP.md](ROADMAP.md): phases, and the checks between them
- [rankify/cli/CLI.md](rankify/cli/CLI.md): the command reference

## Planned stack

Python, packaged with uv. Typer for the CLI, Textual for the terminal UI, numpy for the math, and a local SQLite file for all data.

## References

The books, papers and software that rankify builds on or measures itself against. Entries marked † were checked online for this project. The others are cited from memory, so check the details before you cite them elsewhere.

### Models of comparison and choice

- Thurstone, L. L. (1927). A law of comparative judgment. *Psychological Review*. Perceived quality carries noise, so close items get confused. This is the basis of the benchmark's human judge.
- Bradley, R. A. & Terry, M. E. (1952). Rank analysis of incomplete block designs: the method of paired comparisons. *Biometrika*. The pair model at rankify's core.
- Luce, R. D. (1959). *Individual Choice Behavior: A Theoretical Analysis*. Wiley. The choice axiom behind "pick the best of these".
- Plackett, R. L. (1975). The analysis of permutations. *Applied Statistics*. Extends the model to full orderings ("put these in order").
- † Yellott, J. I. (1977). [The relationship between Luce's choice axiom, Thurstone's theory of comparative judgment, and the double exponential distribution](https://swov.nl/en/publicatie/relationship-between-luces-choice-axiom-thurstones-theory-comparitive-judgment-and). *Journal of Mathematical Psychology* 15. Luce's model is what you get by adding Gumbel noise to each score and taking the best; the benchmark's judges answer picks and orderings this way.
- Davidson, R. R. (1970). On extending the Bradley–Terry model to accommodate ties in paired comparison experiments. *Journal of the American Statistical Association*. How rankify counts "can't decide". The rounds-left forecast uses its expected score and information to work out how many answers a pair needs.
- Debreu, G. (1960). Review of R. D. Luce, *Individual Choice Behavior*. *American Economic Review*. Shows how near-identical options break Luce's axiom.
- Tversky, A. (1972). Elimination by aspects: a theory of choice. *Psychological Review*. Explains why similar items split votes.

### Rating systems built for human judges (benchmark baselines)

- Elo, A. E. (1978). *The Rating of Chessplayers, Past and Present*. Arco.
- Glickman, M. E. (1999). Parameter estimation in large dynamic paired comparison experiments. *Applied Statistics*. The Glicko system, the first to give ratings a deviation.
- Glickman, M. E. (2001). Dynamic paired comparison models with stochastic variances. *Journal of Applied Statistics*. Glicko-2.
- Herbrich, R., Minka, T. & Graepel, T. (2007). TrueSkill: a Bayesian skill rating system. *Advances in Neural Information Processing Systems 19*. Its moment-matching update was how rankify's first rounds-left forecast, a simulation, updated its fit after each simulated answer.
- Weng, R. C. & Lin, C.-J. (2011). A Bayesian approximation method for online ranking. *Journal of Machine Learning Research*. The method behind openskill.
- † LMSYS (2023). [Chatbot Arena: new models & Elo system update](https://lmsys.org/blog/2023-12-07-leaderboard). Chatbot Arena moved from online Elo to a Bradley–Terry fit for more stable ratings.

### Choosing questions and sorting

- Ford, L. R. & Johnson, S. M. (1959). A tournament problem. *American Mathematical Monthly*. Merge insertion, which gets close to the fewest comparisons a sort can use.
- † Houlsby, N., Huszár, F., Ghahramani, Z. & Lengyel, M. (2011). [Bayesian active learning for classification and preference learning](https://arxiv.org/abs/1112.5745). BALD. rankify's planner uses the same idea, aimed at the order of each pair rather than the scores.
- † Maystre, L. & Grossglauser, M. (2017). [Just sort it! A simple and effective approach to active preference learning](https://proceedings.mlr.press/v70/maystre17a.html). *ICML*. Repeated quicksort; the strong reference baseline.
- † MacKay, D. J. C. (1992). [Information-based objective functions for active data selection](https://mlanthology.org/neco/1992/mackay1992neco-informationbased). *Neural Computation* 4(4). Expected information from a Gaussian (Laplace) posterior. rankify scores picks and orderings the same way: the answer's expected Fisher information shrinks the posterior, and the planner counts how much less uncertain each pair's order becomes.
- † Saha, A. & Gopalan, A. (2019). [Active ranking with subset-wise preferences](https://arxiv.org/abs/1810.10321). *AISTATS*. Finds that "pick the best" is no faster than pairs, while ordering m items is up to m times faster.
- Chen, X., Bennett, P. N., Collins-Thompson, K. & Horvitz, E. (2013). Pairwise ranking aggregation in a crowdsourced setting. *WSDM*. Crowd-BT, which weighs judges by reliability. Relevant once many people rank one list.

### How people answer (the benchmark's human judge)

- Moyer, R. S. & Landauer, T. K. (1967). Time required for judgements of numerical inequality. *Nature*. The distance effect: close calls take longer.
- † Cox, D. R. (1958). [Two further applications of a model for binary regression](https://sugaku.net/oa/W2060374620). *Biometrika* 45(3–4). The calibration slope: rankify fits one to your answers against what it expected before each, to learn how decisive you are, for the rounds-left forecast and to widen the fit's gaps by what the answers surely show.
- Wichmann, F. A. & Hill, N. J. (2001). The psychometric function: I. Fitting, sampling, and goodness of fit. *Perception & Psychophysics*. Lapses, the occasional answer given at random.

### Calibrating the human judge

- Efron, B. & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall. The parametric bootstrap bias correction used by `rankify calibrate`.
- Fuller, W. A. (1987). *Measurement Error Models*. Wiley. Errors in variables: why noisy estimated gaps weaken the relationships measured against them.

### Learning how much an answer counts

- MacKay, D. J. C. (1992). Bayesian interpolation. *Neural Computation*. The evidence framework: rankify learns its prior width by maximizing the evidence.
- Dempster, A. P., Laird, N. M. & Rubin, D. B. (1977). Maximum likelihood from incomplete data via the EM algorithm. *Journal of the Royal Statistical Society, Series B*. The algorithm that finds that width.
- † Tierney, L. & Kadane, J. B. (1986). [Accurate approximations for posterior moments and marginal densities](https://doi.org/10.1080/01621459.1986.10478240). *Journal of the American Statistical Association* 81(393). The Laplace approximation behind rankify's fit; the rounds-left forecast follows where it moves after n more answers.
- † Woodbury, M. A. (1950). [Inverting modified matrices](https://en.wikipedia.org/wiki/Woodbury_matrix_identity). Memorandum Report 42, Statistical Research Group, Princeton University. How the forecast adds many pairs' answers to the fit's covariance in one step.
- Abramowitz, M. & Stegun, I. A. (1964). *Handbook of Mathematical Functions*. National Bureau of Standards. Formula 7.1.26, the forecast's normal curve (measured error under 1e-7).
- Aitken, A. C. (1926). On Bernoulli's numerical solution of algebraic equations. *Proceedings of the Royal Society of Edinburgh*. Aitken's acceleration, tried first to speed up the EM steps. It ran the wrong way when the best width was far from the start, so rankify uses secant steps that must agree with the EM step.
- † Minka, T. P. (2001). [Expectation propagation for approximate Bayesian inference](https://arxiv.org/abs/1301.2294). *Proceedings of UAI 2001*. EP: the fit under test to replace Laplace's. It matches what each answer implies about the scores' mean and spread, not only where they peak.
- † Kuss, M. & Rasmussen, C. E. (2005). [Assessing approximate inference for binary Gaussian process classification](https://www.jmlr.org/papers/v6/kuss05a.html). *Journal of Machine Learning Research* 6. On yes/no data, Laplace's approximation comes out too narrow and too close to the middle, and EP close to exact. rankify's Laplace fit did the same with judges who seldom contradict themselves: it learned the scores' spread about 5 times too small.
- † Chu, W. & Ghahramani, Z. (2005). [Preference learning with Gaussian processes](https://mlg.eng.cam.ac.uk/zoubin/papers/icml05chuwei-pl.pdf). *ICML*. Bayesian learning from pair preferences. `choix`'s EP, the reference the EP fit is tested against, follows it.
- † Walker, H. F. & Ni, P. (2011). [Anderson acceleration for fixed-point iterations](https://doi.org/10.1137/10078356X). *SIAM Journal on Numerical Analysis* 49(4). Speeds up how the EP fit learns the prior width, the first-slot bonus and the tie weight together. With one value it is the secant method.
- † Liu, Q. & Pierce, D. A. (1994). [A note on Gauss–Hermite quadrature](https://doi.org/10.2307/2337136). *Biometrika* 81(3). Quadrature centred on the peak, which the EP fit uses for an answer when it is already fairly sure of the gap.
- † Trefethen, L. N. & Weideman, J. A. C. (2014). [The exponentially convergent trapezoidal rule](https://doi.org/10.1137/130932132). *SIAM Review* 56(3). Why an evenly spaced grid is accurate to about 1e-15 for smooth curves. The EP fit uses one when it is unsure of a gap, after taking out the sharp step in closed form.

### Software

- † [choix](https://pypi.org/project/choix/) (Maystre): Bradley–Terry and Plackett–Luce fits. Our reference in tests.
- † [Textual](https://pypi.org/project/textual/) (Textualize): the terminal UI behind `rankify play`.
- † [openskill](https://pypi.org/project/openskill/), † [trueskill](https://pypi.org/project/trueskill/) and † [glicko2](https://pypi.org/project/glicko2/): the rating systems in the benchmark.
- † [corsort](https://pypi.org/project/corsort): research on sorts that give a useful result when stopped early.

## License

[MIT](LICENSE)
