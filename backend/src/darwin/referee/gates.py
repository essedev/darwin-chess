"""The gates after build and perft: smoke games and the phase match."""

import time
from dataclasses import dataclass, field
from typing import Any

from darwin.config import Settings
from darwin.referee.match import MatchResult, fixed_match, sprt_match
from darwin.referee.models import FAULTS, EngineSpec, Gate, GateResult
from darwin.referee.sprt import SprtParams, SprtVerdict


@dataclass(frozen=True)
class MatchPolicy:
    params: SprtParams
    tc: str
    batch_pairs: int
    max_pairs: int


@dataclass(frozen=True)
class Policy:
    """How hard each gate tests. Defaults are a first guess, tuned with the M5 load test."""

    perft_positions: int = 8
    perft_depth: int = 3
    smoke_pairs: int = 3
    smoke_tc: str = "2+0.02"
    first_steps: MatchPolicy = field(
        default_factory=lambda: MatchPolicy(SprtParams(0, 150), "2+0.02", 6, 60)
    )
    evolution: MatchPolicy = field(
        default_factory=lambda: MatchPolicy(SprtParams(0, 10), "8+0.08", 12, 1500)
    )


async def smoke_gate(
    settings: Settings, candidate: EngineSpec, opponent: EngineSpec, policy: Policy, seed: int
) -> GateResult:
    started = time.monotonic()
    games = await fixed_match(
        settings, candidate, opponent, tc=policy.smoke_tc, pairs=policy.smoke_pairs, seed=seed
    )
    elapsed = int((time.monotonic() - started) * 1000)
    for game in games:
        if game.termination in FAULTS and game.loser() == candidate.name:
            detail = {"problem": game.termination.value, "pgn": game.pgn}
            return GateResult(Gate.SMOKE, False, detail, elapsed)
    return GateResult(Gate.SMOKE, True, {"games": len(games)}, elapsed)


async def match_gate(
    settings: Settings, candidate: EngineSpec, opponent: EngineSpec, policy: MatchPolicy,
    seed: int,
) -> tuple[GateResult, MatchResult]:  # fmt: skip
    started = time.monotonic()
    result = await sprt_match(
        settings, candidate, opponent, policy.params,
        tc=policy.tc, batch_pairs=policy.batch_pairs, max_pairs=policy.max_pairs, seed=seed,
    )  # fmt: skip
    lower, upper = policy.params.bounds()
    detail: dict[str, Any] = {
        "opponent": opponent.name,
        "games": len(result.games),
        "pentanomial": result.penta,
        "elo": round(result.elo, 1),
        "elo_error": round(result.elo_error, 1),
        "llr": round(result.llr, 3),
        "bounds": [round(lower, 3), round(upper, 3)],
        "elo_bounds": [policy.params.elo0, policy.params.elo1],
        "verdict": "inconclusive" if result.verdict is SprtVerdict.CONTINUE else result.verdict,
    }
    passed = result.verdict is SprtVerdict.H1
    elapsed = int((time.monotonic() - started) * 1000)
    return GateResult(Gate.MATCH, passed, detail, elapsed), result
