"""What each move of a finished Lichess game did to the outcome, from Stockfish's evaluation
of every position (`lichess_games.evals`, written by `referee.analysis.evaluate`).

Moves are judged the way Lichess judges them: on the winning chances they gave away, not on
centipawns, so dropping three pawns in a position that stays won is not a mistake, and the
same three pawns in a level position are a blunder. Derived for the public site, never
stored and never shown to the agent.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

# Lichess caps an evaluation here before turning it into winning chances; a forced mate
# (referee.analysis.MATE) lands on the cap.
CP_CAP = 1000
# Lichess's logistic fit of the result against the evaluation.
SLOPE = 0.00368208
# Winning chances given away (on the scale from -1 to 1), largest first.
THRESHOLDS = (("blunder", 0.3), ("mistake", 0.2), ("inaccuracy", 0.1))
JUDGEMENTS = tuple(name for name, _ in THRESHOLDS)
# Points of the small curve in the list of games.
CURVE_POINTS = 32


def chances(cp: int) -> float:
    """Winning chances from -1 (lost) to 1 (won) for the side the evaluation is from."""
    capped = max(-CP_CAP, min(CP_CAP, cp))
    return 2 / (1 + math.exp(-SLOPE * capped)) - 1


def judge(given_away: float) -> str | None:
    """The judgement of a move that gave away these winning chances, None below them all."""
    for name, threshold in THRESHOLDS:
        if given_away >= threshold:
            return name
    return None


@dataclass(frozen=True)
class Review:
    """The judgement of every move of a game and the totals of each side."""

    # One per move: blunder, mistake, inaccuracy or None.
    judgements: list[str | None]
    # One per move: whether the bot played it.
    ours: list[bool]
    # "us" and "them": how many moves of each judgement, and the average centipawn loss.
    sides: dict[str, dict[str, Any]]
    # The move (its index) that gave away the most winning chances, by either side, when it
    # is at least an inaccuracy: where the game turned.
    turning_point: int | None


def usable(moves: Sequence[str], evals: Sequence[int] | None) -> bool:
    """Evaluations cover the game: one per position, start included."""
    return evals is not None and len(evals) == len(moves) + 1


def review(plies: int, evals: Sequence[int], color: str) -> Review:
    """Judges the first `plies` moves of a game played from the standard start, with
    `evals` from the bot's side (one per position, so at least `plies + 1`)."""
    if len(evals) < plies + 1:
        raise ValueError(f"{len(evals)} evaluations for {plies} moves")
    white = color == "white"
    judgements: list[str | None] = []
    ours: list[bool] = []
    lost_cp: dict[str, list[int]] = {"us": [], "them": []}
    worst: tuple[float, int] | None = None
    for ply in range(plies):
        mine = (ply % 2 == 0) == white  # White moves on even plies from the start
        sign = 1 if mine else -1
        before, after = sign * evals[ply], sign * evals[ply + 1]
        given_away = chances(before) - chances(after)
        judgements.append(judge(given_away))
        ours.append(mine)
        capped = [max(-CP_CAP, min(CP_CAP, cp)) for cp in (before, after)]
        lost_cp["us" if mine else "them"].append(max(0, capped[0] - capped[1]))
        if judgements[-1] and (worst is None or given_away > worst[0]):
            worst = (given_away, ply)
    sides: dict[str, dict[str, Any]] = {}
    for side, lost in lost_cp.items():
        played = [j for j, o in zip(judgements, ours, strict=True) if o == (side == "us")]
        sides[side] = {name: played.count(name) for name in JUDGEMENTS}
        sides[side]["acpl"] = round(sum(lost) / len(lost)) if lost else None
    return Review(judgements, ours, sides, None if worst is None else worst[1])


def curve(evals: Sequence[int], points: int = CURVE_POINTS) -> list[int]:
    """The bot's winning chances in percent (-100 to 100) over the game, at most `points`
    positions evenly spaced, the first and the last always included."""
    if len(evals) <= points:
        picked = list(evals)
    else:
        step = (len(evals) - 1) / (points - 1)
        picked = [evals[round(i * step)] for i in range(points)]
    return [round(100 * chances(cp)) for cp in picked]
