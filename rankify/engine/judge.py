"""A simulated person answering pair rounds. Used by the benchmark and by calibration.

Each answer perceives the two items' scores with normal noise (Thurstone 1927). On top of
that: noise grows with fatigue, a lean toward the item shown first, occasional answers at
random (lapses; Wichmann & Hill 2001), "can't decide" on near-ties, and slower answers on
close calls (the distance effect; Moyer & Landauer 1967).
"""

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

_PHI = NormalDist()
_SQRT2 = math.sqrt(2.0)


@dataclass(frozen=True)
class HumanParams:
    """How the simulated person answers. The defaults are guesses; `rankify calibrate`
    measures them from a real session."""

    noise: float = 1.0  # spread of the perceived score per answer
    fatigue: float = 0.003  # noise grows by this share per round...
    fatigue_cap: float = 1.6  # ...up to this multiple
    first_bonus: float = 0.15  # leans toward the item shown first
    lapse: float = 0.03  # share of answers given at random
    tie_peak: float = 0.3  # chance of "can't decide" when two items are equal...
    tie_width: float = 0.3  # ...falling off as the gap grows
    base_seconds: float = 2.0  # time to answer an easy pair
    close_seconds: float = 3.0  # extra time on a close call...
    close_width: float = 0.6  # ...falling off as the gap grows
    tie_seconds: float = 1.0  # extra time before saying "can't decide"


def human_answer(
    p: HumanParams, rng: np.random.Generator, diff: float, round_no: int
) -> tuple[int | None, float]:
    """One answer to a pair whose first item is ``diff`` better than the second.

    Returns (1 or 2 for the item picked, or None for "can't decide"; seconds taken).
    """
    gap = abs(diff)
    seconds = (p.base_seconds + p.close_seconds * math.exp(-gap / p.close_width)) * float(
        rng.lognormal(0.0, 0.25)
    )
    if rng.random() < p.lapse:
        return int(rng.integers(1, 3)), seconds
    if rng.random() < p.tie_peak * math.exp(-gap / p.tie_width):
        return None, seconds + p.tie_seconds
    sd = p.noise * min(1.0 + p.fatigue * round_no, p.fatigue_cap)
    p_first = _PHI.cdf((diff + p.first_bonus) / (_SQRT2 * sd))
    return (1 if rng.random() < p_first else 2), seconds
