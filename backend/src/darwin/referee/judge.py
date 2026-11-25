"""The referee's single entry point: a genome commit in, a verdict out.

Gates run in order of cost and stop at the first failure. Which gates apply depends on the
phase, which the referee unlocks, not the agent.
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

from darwin.config import Settings
from darwin.referee import engines
from darwin.referee.build import build_gate
from darwin.referee.errors import RefereeError
from darwin.referee.gates import Policy, match_gate, smoke_gate
from darwin.referee.match import MatchResult, OnBatch
from darwin.referee.models import Binary, GateResult
from darwin.referee.perft import perft_gate

log = logging.getLogger(__name__)


class Phase(StrEnum):
    GENESIS = "genesis"  # build and perft only: there is no champion yet
    FIRST_STEPS = "first_steps"  # beat the random player
    EVOLUTION = "evolution"  # beat the champion


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    gates: list[GateResult]
    binary: Binary | None
    match: MatchResult | None


async def judge(
    settings: Settings, commit: str, phase: Phase, *, champion: Binary | None, seed: int,
    policy: Policy | None = None, on_batch: OnBatch | None = None,
) -> Verdict:  # fmt: skip
    policy = policy or Policy()
    if phase is Phase.EVOLUTION and champion is None:
        raise RefereeError("evolution needs a champion")
    gates: list[GateResult] = []

    build, binary = await build_gate(settings, commit)
    gates.append(build)
    if binary is None:
        return Verdict(False, gates, None, None)

    candidate = engines.candidate(settings, binary, name="candidate")
    perft = await perft_gate(
        settings, candidate, seed=seed, positions=policy.perft_positions, depth=policy.perft_depth
    )
    gates.append(perft)
    if not perft.passed or phase is Phase.GENESIS:
        return Verdict(perft.passed, gates, binary, None)

    random_player = engines.random_player(settings)
    smoke = await smoke_gate(settings, candidate, random_player, policy, seed)
    gates.append(smoke)
    if not smoke.passed:
        return Verdict(False, gates, binary, None)

    if phase is Phase.FIRST_STEPS:
        opponent, match_policy = random_player, policy.first_steps
    else:
        assert champion is not None
        opponent = engines.candidate(settings, champion, name="champion")
        match_policy = policy.evolution
    gate, result = await match_gate(settings, candidate, opponent, match_policy, seed, on_batch)
    gates.append(gate)
    log.info("commit %s in %s: %s", commit[:12], phase, "accepted" if gate.passed else "rejected")
    return Verdict(gate.passed, gates, binary, result)
