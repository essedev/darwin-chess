"""The Lichess game being played right now, read from the file the bot keeps up to date.

The bot replaces `<data_dir>/lichess/current.json` atomically on every move; the API only
reads it and adds the board (FEN, SAN, last move) the dashboard draws.
"""

import json
import logging
from pathlib import Path
from typing import Any

import chess

from darwin.api.live import replay

CURRENT = Path("lichess") / "current.json"

log = logging.getLogger(__name__)


def read_lichess_live(data_dir: Path) -> dict[str, Any] | None:
    """The game in progress, or None when there is none (no file, or the game is over)."""
    try:
        state = json.loads((data_dir / CURRENT).read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        # The bot replaces the file atomically, so a broken one is a bug on its side.
        log.warning("unreadable %s: %s", data_dir / CURRENT, error)
        return None
    if not isinstance(state, dict) or state.get("status") != "started":
        return None
    start = state.get("initial_fen") or "startpos"
    start_fen = chess.STARTING_FEN if start == "startpos" else str(start)
    moves = [str(m) for m in state.get("moves") or []]
    try:
        board = replay(start_fen, moves)
    except ValueError as error:
        log.warning(
            "Lichess game %s has an unreadable initial FEN: %s", state.get("game_id"), error
        )
        return None
    return {**state, "initial_fen": start_fen, **board}
