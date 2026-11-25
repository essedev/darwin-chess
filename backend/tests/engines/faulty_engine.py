"""Test engines for the referee, one behaviour per mode (first argument).

- greedy: mates in one if it can, else takes the most valuable piece, else squeezes the
  opponent's mobility. Weak, but it beats the random player almost every game.
- illegal: plays an illegal move from its third move on.
- crash: exits on its third move.
- timeout: stops answering on its third move.
- bad_perft: correct play, but adds one node to the first move of every perft divide.
"""

import sys
import time

import chess
from random_engine import ChooseMove, divide, random_move, serve

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def _opponent_mobility(board: chess.Board, move: chess.Move) -> int:
    board.push(move)
    mobility = board.legal_moves.count()
    board.pop()
    return mobility


def greedy(board: chess.Board) -> chess.Move:
    moves = list(board.legal_moves)
    for move in moves:
        if board.gives_check(move):
            board.push(move)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return move
    captures = [move for move in moves if board.is_capture(move)]
    if captures:

        def gain(move: chess.Move) -> int:
            victim = board.piece_at(move.to_square)
            return VALUES.get(victim.piece_type, 1) if victim else 1  # None: en passant

        return max(captures, key=gain)
    return min(moves, key=lambda move: _opponent_mobility(board, move))


def illegal(board: chess.Board) -> chess.Move:
    legal = set(board.legal_moves)
    for from_square in chess.SQUARES:
        for to_square in chess.SQUARES:
            move = chess.Move(from_square, to_square)
            if from_square != to_square and move not in legal:
                return move
    raise RuntimeError("no illegal move found")


def after_two_moves(fault: str) -> ChooseMove:
    played = 0

    def choose(board: chess.Board) -> chess.Move:
        nonlocal played
        played += 1
        if played < 3:
            return random_move(board)
        if fault == "illegal":
            return illegal(board)
        if fault == "crash":
            sys.exit(3)
        time.sleep(3600)
        return random_move(board)

    return choose


def bad_divide(board: chess.Board, depth: int) -> dict[str, int]:
    counts = divide(board, depth)
    first = next(iter(counts))
    counts[first] += 1
    return counts


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "greedy":
        serve("greedy", greedy)
    elif mode == "bad_perft":
        serve("bad-perft", random_move, bad_divide)
    elif mode in {"illegal", "crash", "timeout"}:
        serve(mode, after_two_moves(mode))
    else:
        raise SystemExit(f"unknown mode {mode}")
