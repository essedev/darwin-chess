from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Gate(StrEnum):
    BUILD = "build"
    PERFT = "perft"
    SMOKE = "smoke"
    MATCH = "match"


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    passed: bool
    # Public detail: this is all the agent ever sees of the referee's work.
    detail: dict[str, Any]
    duration_ms: int


@dataclass(frozen=True)
class Binary:
    """A compiled genome commit, stored under the data dir as `<dir>/genome`."""

    commit: str
    dir: Path

    @property
    def path(self) -> Path:
        return self.dir / "genome"


@dataclass(frozen=True)
class Mount:
    host: Path
    container: str


@dataclass(frozen=True)
class EngineSpec:
    """How to start one engine process in its own container."""

    name: str
    image: str
    command: tuple[str, ...]
    mounts: tuple[Mount, ...] = field(default=())
    options: tuple[tuple[str, str], ...] = field(default=())  # UCI setoption, via fastchess


class Termination(StrEnum):
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    REPETITION = "repetition"
    FIFTY_MOVES = "fifty_moves"
    MATERIAL = "material"
    ADJUDICATION = "adjudication"
    ILLEGAL_MOVE = "illegal_move"
    TIMEOUT = "timeout"
    CRASH = "crash"


# Terminations that mean an engine broke the contract, not that it lost at chess.
FAULTS = frozenset({Termination.ILLEGAL_MOVE, Termination.TIMEOUT, Termination.CRASH})


@dataclass(frozen=True)
class GameRecord:
    white: str
    black: str
    result: str  # "1-0", "0-1", "1/2-1/2"
    termination: Termination
    start_fen: str
    pgn: str

    def score_for(self, name: str) -> float:
        if self.result == "1/2-1/2":
            return 0.5
        white_won = self.result == "1-0"
        return 1.0 if white_won == (self.white == name) else 0.0

    def loser(self) -> str | None:
        if self.result == "1-0":
            return self.black
        if self.result == "0-1":
            return self.white
        return None
