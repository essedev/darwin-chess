"""Perft gate: the candidate's move generator against python-chess on random positions.

Positions come from random playouts, also from a few tactical seeds (castling, en passant,
promotions), so their counts cannot be known in advance and written by hand.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any

import chess

from darwin.config import Settings
from darwin.referee import uci
from darwin.referee.models import EngineSpec, Gate, GateResult

SEEDS = (
    chess.STARTING_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
)
PERFT_TIMEOUT_S = 30.0


def random_positions(rng: random.Random, count: int) -> list[str]:
    fens: list[str] = []
    while len(fens) < count:
        board = chess.Board(rng.choice(SEEDS))
        for _ in range(rng.randint(2, 40)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if not board.is_game_over() and board.fen() not in fens:
            fens.append(board.fen())
    return fens


def _count(board: chess.Board, depth: int) -> int:
    if depth <= 1:
        return board.legal_moves.count() if depth == 1 else 1
    total = 0
    for move in board.legal_moves:
        board.push(move)
        total += _count(board, depth - 1)
        board.pop()
    return total


def reference_divide(fen: str, depth: int) -> dict[str, int]:
    board = chess.Board(fen)
    counts: dict[str, int] = {}
    for move in board.legal_moves:
        board.push(move)
        counts[move.uci()] = _count(board, depth - 1)
        board.pop()
    return counts


@dataclass(frozen=True)
class Divide:
    counts: dict[str, int]
    total: int


def parse_divide(lines: list[str]) -> Divide:
    """`<move>: <count>` lines then `total: <count>`; other lines (info, logs) are ignored."""
    counts: dict[str, int] = {}
    total = -1
    for line in lines:
        key, sep, value = line.partition(":")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if not value.isdigit():
            continue
        if key == "total":
            total = int(value)
        elif 4 <= len(key) <= 5:
            counts[key] = int(value)
    return Divide(counts, total)


def compare(fen: str, depth: int, expected: dict[str, int], got: Divide) -> dict[str, Any] | None:
    """The first discrepancy, as public detail for the agent; None if the divide matches."""
    base: dict[str, Any] = {"fen": fen, "depth": depth}
    missing = sorted(set(expected) - set(got.counts))
    if missing:
        return {**base, "problem": "missing_moves", "moves": missing}
    extra = sorted(set(got.counts) - set(expected))
    if extra:
        return {**base, "problem": "illegal_moves", "moves": extra}
    for move in sorted(expected):
        if got.counts[move] != expected[move]:
            return {**base, "problem": "wrong_count", "move": move,
                    "expected": expected[move], "got": got.counts[move]}  # fmt: skip
    if got.total != sum(expected.values()):
        return {**base, "problem": "wrong_total", "expected": sum(expected.values()),
                "got": got.total}  # fmt: skip
    return None


async def check(
    settings: Settings, spec: EngineSpec, fens: list[str], depth: int
) -> dict[str, Any] | None:
    """Runs perft on every position; returns the first discrepancy or None."""
    async with uci.session(settings, spec) as engine:
        for fen in fens:
            expected = await asyncio.to_thread(reference_divide, fen, depth)
            engine.send(f"position fen {fen}")
            engine.send(f"perft {depth}")
            got = parse_divide(await engine.read_until("total:", PERFT_TIMEOUT_S))
            problem = compare(fen, depth, expected, got)
            if problem is not None:
                return problem
    return None


async def perft_gate(
    settings: Settings, spec: EngineSpec, *, seed: int, positions: int = 8, depth: int = 3
) -> GateResult:
    started = time.monotonic()
    fens = random_positions(random.Random(seed), positions)
    try:
        problem = await check(settings, spec, fens, depth)
    except uci.EngineFault as fault:
        problem = {"problem": "protocol", "message": str(fault)}
    elapsed = int((time.monotonic() - started) * 1000)
    if problem is None:
        return GateResult(Gate.PERFT, True, {"positions": len(fens), "depth": depth}, elapsed)
    return GateResult(Gate.PERFT, False, problem, elapsed)
