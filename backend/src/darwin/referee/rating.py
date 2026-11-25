"""Absolute Elo of a champion, from matches against Stockfish at limited strength.

The ladder starts at the weakest anchor and climbs while the champion wins too clearly for
a match to measure anything. Every anchor whose score is informative (neither a whitewash
nor a rout) gives an estimate; they are combined weighting each by its precision.
"""

import math
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


async def rate(
    settings: Settings, champion: EngineSpec, *, pairs: int, tc: str, seed: int
) -> Rating:
    results: list[AnchorResult] = []
    for anchor in LADDER:
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
        result = AnchorResult(anchor, sum(scores) / (2 * len(scores)), diff, error)
        results.append(result)
        if result.score < INFORMATIVE[1]:
            break  # this anchor is strong enough: no need to climb further
    return combine(results)
