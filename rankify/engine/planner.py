"""Choosing the next round.

Phase 1 picks a random pair. Phase 2 replaces this with information gain per second.
"""

import numpy as np

PLANNER_NAME = "random-pair-0.1"


def derive_seed(*parts: int) -> int:
    """A 63-bit seed from integer parts, so it fits in a SQLite INTEGER."""
    state = np.random.SeedSequence([int(p) for p in parts]).generate_state(1, dtype=np.uint64)
    return int(state[0] >> np.uint64(1))


def random_pair(candidates: np.ndarray, seed: int) -> tuple[int, int]:
    """Two different candidates, in random display order."""
    if len(candidates) < 2:
        raise ValueError("need at least two items to make a pair")
    rng = np.random.default_rng(seed)
    first, second = rng.choice(np.asarray(candidates), size=2, replace=False)
    return int(first), int(second)
