import numpy as np
import pytest

from rankify import store
from rankify.service import NothingToAsk, Rankify


@pytest.fixture
def conn(tmp_path):
    c = store.connect(tmp_path / "test.db")
    yield c
    c.close()


@pytest.fixture
def rk(conn):
    return Rankify(conn)


class SimulatedJudge:
    """Answers rounds by Bradley-Terry (pairs) and Plackett-Luce (picks and rankings) with
    hidden true scores, keyed by item name."""

    def __init__(self, truth: dict[str, float], seed: int):
        self.truth = truth
        self.rng = np.random.default_rng(seed)

    def pick(self, names: list[str]) -> int:
        a, b = (self.truth[n] for n in names)
        p_first = 1.0 / (1.0 + np.exp(-(a - b)))
        return 1 if self.rng.random() < p_first else 2

    def answer(self, kind: str, names: list[str]) -> list[int]:
        if kind == "pair":
            return [self.pick(names)]
        noisy = np.array([self.truth[n] for n in names]) + self.rng.gumbel(size=len(names))
        order = [int(k) + 1 for k in np.argsort(-noisy)]
        return order if kind == "rank" else order[:1]


def first_listed(view) -> list[int]:
    """An answer that prefers items in the order shown, for any kind of round."""
    return list(range(1, len(view.items) + 1)) if view.kind == "rank" else [1]


def run_rounds(
    rk: Rankify, slug: str, judge: SimulatedJudge, rounds: int, mode: str | None = None
) -> list[tuple[str, str]]:
    """Answer up to ``rounds`` rounds; stops early when rankify has nothing left to ask."""
    asked = []
    for _ in range(rounds):
        try:
            view = rk.next_round(slug, mode=mode)
        except NothingToAsk:
            break
        names = [i.name for i in view.items]
        asked.append(tuple(names))
        rk.answer(slug, judge.answer(view.kind, names), round_seq=view.round)
    return asked


def kendall_tau(order: list[str], truth: dict[str, float]) -> float:
    """+1 when ``order`` (best first) agrees with the truth on every pair, -1 when reversed."""
    concordant = discordant = 0
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            if truth[order[i]] > truth[order[j]]:
                concordant += 1
            else:
                discordant += 1
    return (concordant - discordant) / (concordant + discordant)
