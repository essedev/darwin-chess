"""The game being played right now, read from the newest fastchess event stream.

fastchess writes one NDJSON line per move while the match runs; the API only reads it.
Several games run in parallel: the dashboard follows the newest one still in progress.
"""

import json
from collections.abc import Iterable
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
        board = chess.Board(self.start_fen)
        san: list[str] = []
        for uci in self.moves:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                break  # the referee will reject it; show the game up to there
            san.append(board.san(move))
            board.push(move)
        return {
            "match": self.match,
            "game": self.game,
            "white": self.white,
            "black": self.black,
            "fen": board.fen(),
            "san": san,
            "start_ply": _ply(self.start_fen),
            "last_move": self.moves[len(san) - 1] if san else None,
            "result": self.result,
            "termination": self.termination,
        }


def _ply(fen: str) -> int:
    board = chess.Board(fen)
    return (board.fullmove_number - 1) * 2 + (0 if board.turn == chess.WHITE else 1)


def newest_match(matches_dir: Path) -> Path | None:
    streams = list(matches_dir.glob("*/events.ndjson"))
    return max(streams, key=lambda p: p.stat().st_mtime) if streams else None


def read_live_game(matches_dir: Path) -> dict[str, Any] | None:
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
    running = [g for g in games.values() if g.result is None]
    chosen = max(running or games.values(), key=lambda g: g.game)
    return {**chosen.view(), "tally": _tally(games.values())}


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
