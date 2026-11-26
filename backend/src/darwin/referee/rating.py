"""Absolute Elo of a champion, from matches against Stockfish at limited strength.

With an expected Elo (the previous champion's plus the gain that promoted the new one) the
ladder starts at the rungs just below and just above it; without one, at the weakest anchor.
It then climbs while the highest rung played is still a whitewash and steps down while the
lowest is a rout. Every anchor whose score is informative (neither a whitewash nor a rout)
gives an estimate; they are combined weighting each by its precision.
"""

import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from darwin.config import Settings
from darwin.referee import engines
from darwin.referee.match import fixed_match, pair_scores
from darwin.referee.models import EngineSpec
from darwin.referee.sprt import elo_estimate, pentanomial

LADDER = (1320, 1600, 2000, 2400, 2800)
INFORMATIVE = (0.1, 0.9)  # mean score range in which an anchor measures something


@dataclass(frozen=True)
class AnchorResult:
    anchor_elo: int
    score: float
    elo_diff: float
    error: float  # 95% half-width of elo_diff
    games: int

    @property
    def informative(self) -> bool:
        return INFORMATIVE[0] < self.score < INFORMATIVE[1]


@dataclass(frozen=True)
class Rating:
    elo: float | None  # None when the champion is below the ladder
    error: float | None
    below_scale: bool
    anchors: list[AnchorResult]

    def detail(self) -> dict[str, Any]:
        return {
            "below_scale": self.below_scale,
            "anchors": [
                {
                    "elo": a.anchor_elo,
                    "score": round(a.score, 3),
                    "elo_diff": round(a.elo_diff, 1),
                    "error": round(a.error, 1),
                    "games": a.games,
                }
                for a in self.anchors
            ],
        }


def combine(results: list[AnchorResult]) -> Rating:
    useful = [r for r in results if r.informative and math.isfinite(r.error) and r.error > 0]
    below = bool(results) and results[0].score <= INFORMATIVE[0] and not useful
    if not useful:
        return Rating(None, None, below, results)
    weights = [1 / (r.error**2) for r in useful]
    elo = sum(w * (r.anchor_elo + r.elo_diff) for w, r in zip(weights, useful, strict=True))
    return Rating(elo / sum(weights), 1 / math.sqrt(sum(weights)), False, results)


def first_rungs(expected: float | None) -> list[int]:
    """The rungs just below and just above the expected Elo (one at either end of the
    ladder), or the weakest anchor when nothing is expected."""
    if expected is None:
        return [LADDER[0]]
    below = [anchor for anchor in LADDER if anchor <= expected][-1:]
    above = [anchor for anchor in LADDER if anchor > expected][:1]
    return below + above


def next_rung(results: list[AnchorResult]) -> int | None:
    """One rung up while the highest played is a whitewash, one down while the lowest is a
    rout; None when both ends measure something or the ladder ends."""
    played = sorted(results, key=lambda r: r.anchor_elo)
    top, bottom = played[-1], played[0]
    if top.score >= INFORMATIVE[1] and top.anchor_elo != LADDER[-1]:
        return LADDER[LADDER.index(top.anchor_elo) + 1]
    if bottom.score <= INFORMATIVE[0] and bottom.anchor_elo != LADDER[0]:
        return LADDER[LADDER.index(bottom.anchor_elo) - 1]
    return None


async def climb(
    expected: float | None, play: Callable[[int], Awaitable[AnchorResult]]
) -> list[AnchorResult]:
    """Every rung the ladder plays, lowest first."""
    results = [await play(anchor) for anchor in first_rungs(expected)]
    while (anchor := next_rung(results)) is not None:
        results.append(await play(anchor))
    return sorted(results, key=lambda r: r.anchor_elo)


async def rate(
    settings: Settings, champion: EngineSpec, *, pairs: int, tc: str, seed: int,
    expected: float | None = None,
) -> Rating:  # fmt: skip
    async def play(anchor: int) -> AnchorResult:
        games = await fixed_match(
            settings,
            champion,
            engines.stockfish(settings, anchor),
            tc=tc,
            pairs=pairs,
            seed=seed + anchor,
        )
        scores = pair_scores(games, champion.name)
        diff, error = elo_estimate(pentanomial(scores))
        return AnchorResult(anchor, sum(scores) / (2 * len(scores)), diff, error, 2 * len(scores))

    return combine(await climb(expected, play))
