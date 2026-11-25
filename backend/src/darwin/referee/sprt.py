"""Pentanomial SPRT on logistic Elo, as in fishtest (the GSPRT approximation `LLR_alt2`).

Results are counted per game pair (same opening, colours swapped): pair scores 0, 0.5, 1,
1.5, 2 from the candidate's point of view. Pairs remove most of the opening noise.
"""

import math
from dataclasses import dataclass
from enum import StrEnum

PAIR_SCORES = (0.0, 0.25, 0.5, 0.75, 1.0)  # pair score / 2


class SprtVerdict(StrEnum):
    H1 = "h1"  # the candidate is better by at least elo1: accept
    H0 = "h0"  # it is not better than elo0: reject
    CONTINUE = "continue"


@dataclass(frozen=True)
class SprtParams:
    elo0: float
    elo1: float
    alpha: float = 0.05
    beta: float = 0.05

    def bounds(self) -> tuple[float, float]:
        lower = math.log(self.beta / (1 - self.alpha))
        upper = math.log((1 - self.beta) / self.alpha)
        return lower, upper


def expected_score(elo: float) -> float:
    return 1 / (1 + 10 ** (-elo / 400))


def pentanomial(pair_scores: list[float]) -> list[int]:
    """Counts of pairs scoring 0, 0.5, 1, 1.5, 2."""
    counts = [0] * 5
    for score in pair_scores:
        counts[round(score * 2)] += 1
    return counts


def _distribution(penta: list[int]) -> tuple[int, float, float]:
    # Like fishtest, a tiny count in empty buckets keeps the variance away from zero.
    regularized = [max(count, 1e-3) for count in penta]
    total = sum(regularized)
    mean = sum(s * c for s, c in zip(PAIR_SCORES, regularized, strict=True)) / total
    var = sum(c * (s - mean) ** 2 for s, c in zip(PAIR_SCORES, regularized, strict=True)) / total
    return sum(penta), mean, var


def llr(penta: list[int], params: SprtParams) -> float:
    pairs, mean, var = _distribution(penta)
    if pairs == 0:
        return 0.0
    s0, s1 = expected_score(params.elo0), expected_score(params.elo1)
    return pairs * (s1 - s0) * (2 * mean - s0 - s1) / var / 2


def decide(value: float, params: SprtParams) -> SprtVerdict:
    lower, upper = params.bounds()
    if value >= upper:
        return SprtVerdict.H1
    if value <= lower:
        return SprtVerdict.H0
    return SprtVerdict.CONTINUE


def elo_estimate(penta: list[int]) -> tuple[float, float]:
    """Elo difference and its 95% half-width, from the pair score distribution."""
    pairs, mean, var = _distribution(penta)
    if pairs == 0:
        return 0.0, math.inf
    clamp = min(max(mean, 1e-6), 1 - 1e-6)
    elo = -400 * math.log10(1 / clamp - 1)
    stderr = math.sqrt(var / pairs)
    low = min(max(clamp - 1.96 * stderr, 1e-6), 1 - 1e-6)
    high = min(max(clamp + 1.96 * stderr, 1e-6), 1 - 1e-6)
    half_width = (-400 * math.log10(1 / high - 1) + 400 * math.log10(1 / low - 1)) / 2
    return elo, half_width
