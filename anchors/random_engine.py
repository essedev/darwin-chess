"""Minimal UCI engine on python-chess: plays a random legal move, answers `perft <depth>`.

It is the referee's first anchor and the base of the faulty engines used in tests, which
reuse `serve` with their own move choice and perft.
"""

import random
import sys
from collections.abc import Callable

import chess

ChooseMove = Callable[[chess.Board], chess.Move]
Divide = Callable[[chess.Board, int], dict[str, int]]


def perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()
    total = 0
    for move in board.legal_moves:
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


def divide(board: chess.Board, depth: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for move in board.legal_moves:
        board.push(move)
        counts[move.uci()] = perft(board, depth - 1)
        board.pop()
    return counts


def random_move(board: chess.Board) -> chess.Move:
    return random.choice(list(board.legal_moves))


def parse_position(tokens: list[str]) -> chess.Board:
    if tokens[0] == "startpos":
        board, rest = chess.Board(), tokens[1:]
    else:  # fen <6 fields> [moves ...]
        board, rest = chess.Board(" ".join(tokens[1:7])), tokens[7:]
    if rest and rest[0] == "moves":
        for uci in rest[1:]:
            board.push_uci(uci)
    return board


def serve(name: str, choose: ChooseMove, perft_divide: Divide = divide) -> None:
    board = chess.Board()
    for raw in sys.stdin:
        tokens = raw.split()
        if not tokens:
            continue
        command = tokens[0]
        if command == "uci":
            print(f"id name {name}\nid author darwin\nuciok", flush=True)
        elif command == "isready":
            print("readyok", flush=True)
        elif command == "ucinewgame":
            board = chess.Board()
        elif command == "position":
            board = parse_position(tokens[1:])
        elif command == "go":
            print(f"bestmove {choose(board).uci()}", flush=True)
        elif command == "perft":
            counts = perft_divide(board, int(tokens[1]))
            lines = [f"{move}: {count}" for move, count in counts.items()]
            lines.append(f"total: {sum(counts.values())}")
            print("\n".join(lines), flush=True)
        elif command == "quit":
            return


if __name__ == "__main__":
    serve("darwin-random", random_move)
