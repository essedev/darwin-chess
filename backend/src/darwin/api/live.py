"""The game being played right now, read from the newest fastchess event stream.

fastchess writes one NDJSON line per move while the match runs; the API only reads it.
Several games run in parallel: the dashboard follows one of them from start to end (see
Follower), so the board does not jump between games.
"""

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess


@dataclass
class LiveGame:
    match: str
    game: int
    white: str
    black: str
    start_fen: str
    moves: list[str] = field(default_factory=list)
    result: str | None = None
    termination: str | None = None

    def view(self) -> dict[str, Any]:
        return {
            "match": self.match,
            "game": self.game,
            "white": self.white,
            "black": self.black,
            **replay(self.start_fen, self.moves),
            "result": self.result,
            "termination": self.termination,
        }


def replay(start_fen: str, moves: list[str]) -> dict[str, Any]:
    """Board after the moves: FEN, SAN list, ply of the start position and the last move.

    Stops at the first move that is not legal (or not UCI at all): the referee rejects it,
    the board shows the game up to there.
    """
    board = chess.Board(start_fen)
    start_ply = (board.fullmove_number - 1) * 2 + (0 if board.turn == chess.WHITE else 1)
    san: list[str] = []
    for uci in moves:
        try:
            move = chess.Move.from_uci(uci)
        except chess.InvalidMoveError:
            break
        if move not in board.legal_moves:
            break
        san.append(board.san(move))
        board.push(move)
    return {
        "fen": board.fen(),
        "san": san,
        "start_ply": start_ply,
        "last_move": moves[len(san) - 1] if san else None,
    }


HOLD_S = 3.0  # the final position of a finished game stays on the board this long


class Follower:
    """Which game the board shows. One game from its start to its end, then its final
    position for a few seconds, then the oldest game still running. Showing the newest game,
    as before, switched the board each time one of the parallel games started."""

    def __init__(self, hold_s: float = HOLD_S, clock: Callable[[], float] = time.monotonic):
        self.hold_s = hold_s
        self.clock = clock
        self.key: tuple[str, int] | None = None
        self.finished_at: float | None = None

    def pick(self, games: list["LiveGame"]) -> "LiveGame":
        by_key = {(g.match, g.game): g for g in games}
        current = by_key.get(self.key) if self.key is not None else None
        if current is not None:
            if current.result is None:
                return current
            now = self.clock()
            if self.finished_at is None:
                self.finished_at = now
            if now - self.finished_at < self.hold_s:
                return current
        running = [g for g in games if g.result is None]
        chosen = min(running, key=lambda g: g.game) if running else max(games, key=lambda g: g.game)
        self.key, self.finished_at = (chosen.match, chosen.game), None
        return chosen


def newest_match(matches_dir: Path) -> Path | None:
    streams = list(matches_dir.glob("*/events.ndjson"))
    return max(streams, key=lambda p: p.stat().st_mtime) if streams else None


def read_live_game(matches_dir: Path, follower: Follower | None = None) -> dict[str, Any] | None:
    """The game to show, with the match's tally. Without a follower (a one-off read): the
    oldest game still running, else the last one."""
    stream = newest_match(matches_dir)
    if stream is None:
        return None
    games: dict[int, LiveGame] = {}
    for line in stream.read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # the last line can be half written
        kind, number = event.get("event"), event.get("game")
        if kind == "game_started":
            games[number] = LiveGame(
                stream.parent.name,
                number,
                event["white"],
                event["black"],
                event.get("start_fen") or chess.STARTING_FEN,
            )
        elif kind == "move" and number in games:
            games[number].moves.append(event["move"])
        elif kind == "game_finished" and number in games:
            games[number].result = event.get("result")
            games[number].termination = event.get("termination")
    if not games:
        return None
    chosen = (follower or Follower(hold_s=0)).pick(list(games.values()))
    # While games of this batch still run, its finished ones are not yet in the trial's
    # progress (the referee counts a batch when it closes): the dashboard adds them.
    running = sum(1 for g in games.values() if g.result is None)
    return {**chosen.view(), "tally": _tally(games.values()), "running": running}


def _tally(games: Iterable[LiveGame]) -> dict[str, dict[str, int]]:
    """Wins, draws and losses so far in this match, per engine name."""
    tally: dict[str, dict[str, int]] = {}
    for game in games:
        if game.result not in {"1-0", "0-1", "1/2-1/2"}:
            continue
        for name, colour_won in ((game.white, "1-0"), (game.black, "0-1")):
            row = tally.setdefault(name, {"wins": 0, "draws": 0, "losses": 0})
            if game.result == "1/2-1/2":
                row["draws"] += 1
            elif game.result == colour_won:
                row["wins"] += 1
            else:
                row["losses"] += 1
    return tally
