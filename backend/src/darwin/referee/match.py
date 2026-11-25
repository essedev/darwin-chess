"""Matches built on the arena: a fixed number of pairs, or an SPRT played in batches.

The SPRT runs fastchess one batch at a time and recomputes the LLR on every game played so
far, stopping at the first bound crossed: the verdict has a single source, this module.
"""

import random
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from darwin.config import Settings
from darwin.referee import arena, openings
from darwin.referee.errors import RefereeError
from darwin.referee.models import EngineSpec, GameRecord
from darwin.referee.sprt import SprtParams, SprtVerdict, decide, elo_estimate, llr, pentanomial


@dataclass(frozen=True)
class MatchResult:
    games: list[GameRecord]
    penta: list[int]
    elo: float
    elo_error: float
    llr: float
    verdict: SprtVerdict  # CONTINUE here means the pair budget ran out: inconclusive
    opponent: str
    tc: str


def pair_scores(games: list[GameRecord], candidate: str) -> list[float]:
    by_opening: dict[str, list[GameRecord]] = defaultdict(list)
    for game in games:
        by_opening[game.start_fen].append(game)
    scores = []
    for fen, pair in by_opening.items():
        if len(pair) != 2:
            raise RefereeError(f"opening {fen} played {len(pair)} times, not 2")
        scores.append(sum(game.score_for(candidate) for game in pair))
    return scores


# Called after every SPRT batch with the match so far (what the public site shows live).
OnBatch = Callable[[dict[str, Any]], Awaitable[None]]


def progress(
    games: list[GameRecord], candidate: str, value: float, params: SprtParams
) -> dict[str, Any]:
    """Games played, the candidate's results and the LLR with its bounds."""
    scores = [game.score_for(candidate) for game in games]
    wins, draws = scores.count(1.0), scores.count(0.5)
    losses = len(scores) - wins - draws
    lower, upper = params.bounds()
    return {
        "games": len(games),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "llr": round(value, 3),
        "bounds": [round(lower, 3), round(upper, 3)],
    }


async def fixed_match(
    settings: Settings, candidate: EngineSpec, opponent: EngineSpec, *, tc: str, pairs: int,
    seed: int,
) -> list[GameRecord]:  # fmt: skip
    book = openings.generate(random.Random(seed), pairs)
    plan = arena.MatchPlan(candidate, opponent, book, tc, settings.match_concurrency)
    return await arena.play(settings, plan)


async def sprt_match(
    settings: Settings, candidate: EngineSpec, opponent: EngineSpec, params: SprtParams, *,
    tc: str, batch_pairs: int, max_pairs: int, seed: int, on_batch: OnBatch | None = None,
) -> MatchResult:  # fmt: skip
    book = openings.generate(random.Random(seed), max_pairs)
    games: list[GameRecord] = []
    value, verdict = 0.0, SprtVerdict.CONTINUE
    for start in range(0, max_pairs, batch_pairs):
        batch = book[start : start + batch_pairs]
        plan = arena.MatchPlan(candidate, opponent, batch, tc, settings.match_concurrency)
        games += await arena.play(settings, plan)
        value = llr(pentanomial(pair_scores(games, candidate.name)), params)
        verdict = decide(value, params)
        if on_batch is not None:
            await on_batch(progress(games, candidate.name, value, params))
        if verdict is not SprtVerdict.CONTINUE:
            break
    penta = pentanomial(pair_scores(games, candidate.name))
    elo, error = elo_estimate(penta)
    return MatchResult(games, penta, elo, error, value, verdict, opponent.name, tc)
