"""The engines the referee puts on the board: candidates, Stockfish anchors, the random player."""

from darwin.config import Settings
from darwin.referee.models import Binary, EngineSpec, Mount

RANDOM_PLAYER = "random"


def candidate(settings: Settings, binary: Binary, name: str | None = None) -> EngineSpec:
    """A genome binary, run in the sandbox image with only its own directory mounted."""
    return EngineSpec(
        name=name or binary.commit[:12],
        image=settings.lab_image,
        command=("/engine/genome",),
        mounts=(Mount(binary.dir, "/engine"),),
    )


def stockfish(settings: Settings, elo: int) -> EngineSpec:
    """Stockfish limited to `elo` (UCI_Elo, calibrated by its authors on CCRL; 1320 minimum)."""
    return EngineSpec(
        name=f"stockfish-{elo}",
        image=settings.anchors_image,
        command=("/usr/games/stockfish",),
        options=(("UCI_LimitStrength", "true"), ("UCI_Elo", str(elo)), ("Hash", "16")),
    )


def random_player(settings: Settings) -> EngineSpec:
    return EngineSpec(
        name=RANDOM_PLAYER,
        image=settings.anchors_image,
        command=("python3", "/anchors/random_engine.py"),
    )
