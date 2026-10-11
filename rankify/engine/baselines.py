"""Other ranking methods, so rankify can be benchmarked against them through the same CLI.

Each method is a pure function of the item positions, the answer history (in log order)
and a seed. Its state is rebuilt by replaying the log, like everything else in rankify.

A history entry is ``(first, second, outcome)``: positions of the two items in display
order, and A_WINS, B_WINS or TIE.
"""

import importlib
import math
import warnings
from dataclasses import dataclass

import numpy as np

from rankify.engine.model import A_WINS, B_WINS
from rankify.engine.planner import derive_seed

History = list[tuple[int, int, int]]

ELO_K = 32.0
ELO_START = 1500.0
ELO_SCALE = 400.0 / math.log(10.0)  # Elo points per natural-log unit


class LogMismatch(ValueError):
    """The log holds an answer this method would never have asked for."""


# ---------------------------------------------------------------- Elo


def elo_ratings(n: int, history: History, k: float = ELO_K) -> np.ndarray:
    """Classic Elo, one match at a time in log order. The result depends on that order."""
    r = np.full(n, ELO_START)
    for a, b, y in history:
        expected = 1.0 / (1.0 + 10.0 ** ((r[b] - r[a]) / 400.0))
        actual = 1.0 if y == A_WINS else 0.0 if y == B_WINS else 0.5
        r[a] += k * (actual - expected)
        r[b] -= k * (actual - expected)
    return r


def elo_close_pair(candidates: np.ndarray, n: int, history: History, seed: int) -> tuple[int, int]:
    """A random item against one of the 3 items with the closest current Elo rating."""
    rng = np.random.default_rng(seed)
    cand = np.asarray(candidates)
    ratings = elo_ratings(n, history)
    i = int(rng.choice(cand))
    others = cand[cand != i]
    gap = np.abs(ratings[others] - ratings[i]) + rng.random(len(others)) * 1e-9
    j = int(rng.choice(others[np.argsort(gap)[:3]]))
    return (i, j) if rng.random() < 0.5 else (j, i)


# ---------------------------------------------------------------- rating systems with uncertainty
#
# Glicko-2, TrueSkill and openskill each keep a mean and a spread per item, updated one
# match at a time. They are third-party packages (development dependencies), imported only
# when used. Each returns (theta, sd) on rankify's natural-log scale, so Score, Confidence
# and Could be are computed the same way for every method.

_SQRT2 = math.sqrt(2.0)


def _need(package: str):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return importlib.import_module(package)
    except ImportError as e:
        raise RuntimeError(
            f"this method needs the '{package}' package; install the dev dependencies (uv sync)"
        ) from e


def glicko2_ratings(n: int, history: History) -> tuple[np.ndarray, np.ndarray]:
    """Glicko-2 (Glickman), one match per rating period, starting at 1500 ± 350."""
    glicko2 = _need("glicko2")
    players = [glicko2.Player() for _ in range(n)]
    for a, b, y in history:
        score = 1.0 if y == A_WINS else 0.0 if y == B_WINS else 0.5
        ra, rda, rb, rdb = players[a].rating, players[a].rd, players[b].rating, players[b].rd
        players[a].update_player([rb], [rdb], [score])
        players[b].update_player([ra], [rda], [1.0 - score])
    rating = np.array([p.rating for p in players])
    rd = np.array([p.rd for p in players])
    return rating / ELO_SCALE, rd / ELO_SCALE


def trueskill_ratings(n: int, history: History) -> tuple[np.ndarray, np.ndarray]:
    """TrueSkill (Herbrich, Minka & Graepel), default settings, draws allowed."""
    ts = _need("trueskill")
    env = ts.TrueSkill(draw_probability=0.05)
    r = [env.create_rating() for _ in range(n)]
    for a, b, y in history:
        if y == B_WINS:
            r[b], r[a] = ts.rate_1vs1(r[b], r[a], env=env)
        else:
            r[a], r[b] = ts.rate_1vs1(r[a], r[b], drawn=(y != A_WINS), env=env)
    return _from_normal_skill([x.mu for x in r], [x.sigma for x in r], env.beta)


def openskill_ratings(n: int, history: History) -> tuple[np.ndarray, np.ndarray]:
    """openskill (Weng & Lin 2011, Plackett-Luce model), default settings."""
    models = _need("openskill.models")
    model = models.PlackettLuce()
    r = [model.rating() for _ in range(n)]
    for a, b, y in history:
        ranks = [1, 2] if y == A_WINS else [2, 1] if y == B_WINS else [1, 1]
        [[r[a]], [r[b]]] = model.rate([[r[a]], [r[b]]], ranks=ranks)
    return _from_normal_skill([x.mu for x in r], [x.sigma for x in r], model.beta)


def _from_normal_skill(mu, sigma, beta: float) -> tuple[np.ndarray, np.ndarray]:
    # These systems use P(a beats b) = Phi((mu_a - mu_b) / (sqrt(2) beta)). The logistic curve
    # with slope 1.702 matches the normal curve closely, which converts mu to rankify's scale.
    k = 1.702 / (_SQRT2 * beta)
    return np.asarray(mu) * k, np.asarray(sigma) * k


# ---------------------------------------------------------------- sorts


@dataclass(frozen=True)
class SortState:
    next_pair: tuple[int, int] | None  # None once the sort is finished
    ranked: list[int]  # sorted so far, best first
    unranked: list[int]  # not placed yet


def _check(entry: tuple[int, int, int], pair: tuple[int, int]) -> bool:
    if (entry[0], entry[1]) != pair:
        raise LogMismatch(f"expected an answer for {pair}, found {entry[:2]}")
    return entry[2] == A_WINS


def insertion_sort(items: list[int], history: History, seed: int) -> SortState:
    """Binary insertion sort that treats every answer as final. A tie counts as a loss."""
    order = [int(x) for x in np.random.default_rng(seed).permutation(items)]
    answers = iter(history)
    ranked: list[int] = []
    for pos, x in enumerate(order):
        lo, hi = 0, len(ranked)
        while lo < hi:
            mid = (lo + hi) // 2
            pair = (x, ranked[mid])
            entry = next(answers, None)
            if entry is None:
                return SortState(pair, ranked, order[pos:])
            if _check(entry, pair):
                hi = mid
            else:
                lo = mid + 1
        ranked.insert(lo, x)
    if next(answers, None) is not None:
        raise LogMismatch("the log has answers after the sort finished")
    return SortState(None, ranked, [])


class _Need(Exception):
    def __init__(self, pair: tuple[int, int]):
        self.pair = pair


def just_sort_it_pair(items: list[int], history: History, seed: int) -> tuple[int, int]:
    """Next comparison of repeated quicksort (Maystre & Grossglauser 2017).

    Pass ``p`` shuffles the items and picks pivots with its own seed. Passes repeat
    forever; the ranking comes from fitting all answers at once, as in the paper.
    """
    if len(items) < 2:
        raise ValueError("need at least two items")
    answers = iter(history)

    def better(x: int, pivot: int) -> bool:
        pair = (x, pivot)
        entry = next(answers, None)
        if entry is None:
            raise _Need(pair)
        return _check(entry, pair)

    def quicksort(xs: list[int], rng: np.random.Generator) -> list[int]:
        if len(xs) <= 1:
            return xs
        pivot = xs[int(rng.integers(len(xs)))]
        top, bottom = [], []
        for x in xs:
            if x != pivot:
                (top if better(x, pivot) else bottom).append(x)
        return quicksort(top, rng) + [pivot] + quicksort(bottom, rng)

    sort_pass = 0
    try:
        while True:
            rng = np.random.default_rng(derive_seed(seed, sort_pass))
            quicksort([int(x) for x in rng.permutation(items)], rng)
            sort_pass += 1
    except _Need as need:
        return need.pair
