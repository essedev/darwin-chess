"""Where a lost game went wrong, according to Stockfish at full strength.

The agent gets the move where the evaluation dropped the most and by how much, never the
better move: a teacher pointing at the mistake, not giving the answer.
"""

import re
from typing import Any

import chess

from darwin.config import Settings
from darwin.referee import uci
from darwin.referee.models import EngineSpec

DEPTH = 12
MATE = 10000
DECIDED_CP = 600  # six pawns: past this the game is decided either way
SCORE = re.compile(r"score (cp|mate) (-?\d+)")


def stockfish_full(settings: Settings) -> EngineSpec:
    return EngineSpec(
        name="stockfish-full", image=settings.anchors_image, command=("/usr/games/stockfish",)
    )


def _score(lines: list[str]) -> int:
    """Centipawns for the side to move, from the last `score` of the search."""
    found = [SCORE.search(line) for line in lines]
    last = [match for match in found if match][-1:]
    if not last:
        return 0
    kind, value = last[0].group(1), int(last[0].group(2))
    if kind == "mate":
        return MATE if value > 0 else -MATE
    return value


async def worst_move(settings: Settings, moves: list[str], our_color: str) -> dict[str, Any]:
    """The move of ours after which our evaluation fell the most."""
    board = chess.Board()
    ours = chess.WHITE if our_color == "white" else chess.BLACK
    evals: list[int] = []  # from our point of view, one per position
    async with uci.session(settings, stockfish_full(settings)) as engine:
        for ply in range(len(moves) + 1):
            if board.is_game_over():
                outcome = board.outcome()
                winner = outcome.winner if outcome else None
                evals.append(0 if winner is None else (MATE if winner == ours else -MATE))
            else:
                engine.send(f"position startpos moves {' '.join(moves[:ply])}".rstrip())
                engine.send(f"go depth {DEPTH}")
                score = _score(await engine.read_until("bestmove", 60))
                evals.append(score if board.turn == ours else -score)
            if ply < len(moves):
                board.push_uci(moves[ply])
    return worst_drop(moves, evals, ours)


def worst_drop(moves: list[str], evals: list[int], ours: chess.Color) -> dict[str, Any]:
    """The move of ours that cost the most, on evaluations clamped to +-DECIDED_CP: once a
    game is decided, sliding from "lost" to "mated" is not the mistake worth showing, the
    move that got there is. Ties go to the earliest move."""
    board = chess.Board()
    worst: dict[str, Any] = {}
    for ply, uci_move in enumerate(moves):
        move = chess.Move.from_uci(uci_move)
        if board.turn == ours:
            before = max(-DECIDED_CP, min(DECIDED_CP, evals[ply]))
            after = max(-DECIDED_CP, min(DECIDED_CP, evals[ply + 1]))
            drop = before - after
            if not worst or drop > worst["drop_cp"]:
                worst = {
                    "move_number": board.fullmove_number,
                    "move": board.san(move),
                    "eval_before_cp": evals[ply],
                    "eval_after_cp": evals[ply + 1],
                    "drop_cp": drop,
                    "fen_before": board.fen(),
                }
        board.push(move)
    return worst
