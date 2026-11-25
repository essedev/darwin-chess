import io
import json
from pathlib import Path

import chess.pgn
import pytest

from darwin.referee.arena import read_games, verify
from darwin.referee.errors import RefereeError
from darwin.referee.match import pair_scores
from darwin.referee.models import Termination

FOOLS_MATE = "1. f3 e5 2. g4 Qh4# 0-1"


def pgn(moves: str, result: str, game_id: int = 1, white: str = "a", black: str = "b") -> str:
    return (
        f'[White "{white}"]\n[Black "{black}"]\n[Result "{result}"]\n[GameId "{game_id}"]\n\n'
        f"{moves}\n\n"
    )


def game(text: str) -> chess.pgn.Game:
    parsed = chess.pgn.read_game(io.StringIO(text))
    assert parsed is not None
    return parsed


def test_checkmate_is_verified_on_the_board() -> None:
    record = verify(game(pgn(FOOLS_MATE, "0-1")), "normal")
    assert record.termination is Termination.CHECKMATE
    assert record.loser() == "a"


def test_a_result_the_board_does_not_support_is_rejected() -> None:
    with pytest.raises(RefereeError, match="checkmate scored"):
        verify(game(pgn(FOOLS_MATE.replace("0-1", "1-0"), "1-0")), "normal")
    with pytest.raises(RefereeError, match="without a rule"):
        verify(game(pgn("1. e4 e5 1/2-1/2", "1/2-1/2")), "normal")


def test_faults_keep_fastchess_termination() -> None:
    record = verify(game(pgn("1. e4 e5 1-0", "1-0")), "illegal_move")
    assert record.termination is Termination.ILLEGAL_MOVE
    assert verify(game(pgn("1. e4 0-1", "0-1")), "stall").termination is Termination.TIMEOUT
    assert verify(game(pgn("1. e4 0-1", "0-1")), "disconnect").termination is Termination.CRASH
    with pytest.raises(RefereeError):
        verify(game(pgn("1. e4 *", "*")), "interrupted")


def test_illegal_moves_in_the_pgn_are_rejected() -> None:
    with pytest.raises(RefereeError, match="unreadable"):
        verify(game(pgn("1. e4 e4 1-0", "1-0")), "illegal_move")


def test_read_games_joins_pgn_and_events(tmp_path: Path) -> None:
    (tmp_path / "games.pgn").write_text(
        pgn(FOOLS_MATE, "0-1", 1, "a", "b") + pgn("1. e4 e5 1-0", "1-0", 2, "b", "a")
    )
    events = [
        {"event": "game_finished", "pgn_game_id": 1, "termination": "normal"},
        {"event": "game_finished", "pgn_game_id": 2, "termination": "time_forfeit"},
    ]
    (tmp_path / "events.ndjson").write_text("\n".join(json.dumps(e) for e in events))
    games = read_games(tmp_path)
    assert [g.termination for g in games] == [Termination.CHECKMATE, Termination.TIMEOUT]
    assert pair_scores(games, "a") == [0.0]  # same start position: one pair, both lost by a


def test_pair_scores_require_complete_pairs(tmp_path: Path) -> None:
    record = verify(game(pgn(FOOLS_MATE, "0-1")), "normal")
    with pytest.raises(RefereeError, match="played 1 times"):
        pair_scores([record], "a")
