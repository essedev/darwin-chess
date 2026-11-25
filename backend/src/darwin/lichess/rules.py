"""Pure decisions of the Lichess bot: whose turn it is, how a game ended, which challenges to
take and which bot to challenge. No I/O, so each one is tested on its own."""

import random
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import chess

STARTPOS = "startpos"
MIN_CLOCK_S = 60
MAX_CLOCK_S = 600
RATING_WINDOW = 300
WIDE_RATING_WINDOW = 600
DEFAULT_RATING = 1500
UNFINISHED = frozenset({"created", "started"})
ABORTED = frozenset({"aborted", "noStart"})


def speed_of(clock_s: int, increment_s: int) -> str:
    """The Lichess speed of a clock, from its estimated duration (limit + 40 increments)."""
    total = clock_s + 40 * increment_s
    if total < 30:
        return "ultraBullet"
    if total < 180:
        return "bullet"
    if total < 480:
        return "blitz"
    if total < 1500:
        return "rapid"
    return "classical"


def board_for(initial_fen: str, moves: Sequence[str]) -> chess.Board:
    board = chess.Board() if initial_fen == STARTPOS else chess.Board(initial_fen)
    for move in moves:
        board.push_uci(move)
    return board


def our_turn(initial_fen: str, plies: int, color: str) -> bool:
    white_first = initial_fen == STARTPOS or chess.Board(initial_fen).turn == chess.WHITE
    white_to_move = white_first == (plies % 2 == 0)
    return white_to_move == (color == "white")


def is_legal(board: chess.Board, uci: str) -> bool:
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:  # "(none)", "0000", garbage
        return False
    return move in board.legal_moves


def result_for(status: str, winner: str | None, color: str) -> str | None:
    """win, loss, draw or aborted from our side; None while the game goes on."""
    if status in UNFINISHED:
        return None
    if status in ABORTED:
        return "aborted"
    if winner not in {"white", "black"}:
        return "draw"
    return "win" if winner == color else "loss"


def position_command(initial_fen: str, moves: Sequence[str]) -> str:
    base = "position startpos" if initial_fen == STARTPOS else f"position fen {initial_fen}"
    return f"{base} moves {' '.join(moves)}" if moves else base


def go_command(
    *, wtime: int, btime: int, winc: int, binc: int, color: str, overhead_ms: int
) -> str:
    """`go` with the Lichess clocks; our own clock loses the network overhead, so an engine
    that spends all it is told does not flag."""
    if color == "white":
        wtime = max(100, wtime - overhead_ms)
    else:
        btime = max(100, btime - overhead_ms)
    return f"go wtime {wtime} btime {btime} winc {winc} binc {binc}"


def decline_reason(challenge: Mapping[str, Any], *, busy: bool) -> str | None:
    """The reason to decline a challenge with (one Lichess accepts), or None to accept it."""
    if (challenge.get("variant") or {}).get("key") != "standard":
        return "variant"
    clock = challenge.get("timeControl") or {}
    limit = clock.get("limit")
    if clock.get("type") != "clock" or not isinstance(limit, int):
        return "timeControl"
    if not MIN_CLOCK_S <= limit <= MAX_CLOCK_S:
        return "timeControl"
    if busy:
        return "later"
    return None


def rating_of(user: Mapping[str, Any], speed: str) -> int | None:
    perf = (user.get("perfs") or {}).get(speed) or {}
    rating = perf.get("rating")
    return int(rating) if isinstance(rating, int | float) else None


def pick_opponent(
    bots: Iterable[Mapping[str, Any]],
    *,
    me: str,
    my_rating: int,
    speed: str,
    rng: random.Random,
) -> str | None:
    """A random online bot rated within RATING_WINDOW of us in `speed`, or within the wide
    window when nobody is that close. Never ourselves, never a flagged account."""
    rated: list[tuple[str, int]] = []
    for bot in bots:
        name = str(bot.get("username") or bot.get("id") or "")
        rating = rating_of(bot, speed)
        if not name or name.lower() == me.lower() or rating is None:
            continue
        if bot.get("tosViolation") or bot.get("disabled"):
            continue
        rated.append((name, rating))
    for window in (RATING_WINDOW, WIDE_RATING_WINDOW):
        pool = sorted(name for name, rating in rated if abs(rating - my_rating) <= window)
        if pool:
            return rng.choice(pool)
    return None
