"""The end of a Lichess game without Docker: Stockfish is replaced by fixed evaluations."""

from pathlib import Path
from typing import Any, cast

import pytest

from darwin.config import Settings
from darwin.ledger import lichess as records
from darwin.ledger.store import Ledger
from darwin.lichess import game as game_module
from darwin.lichess.client import LichessClient
from darwin.lichess.game import Game, LiveGame
from darwin.lichess.rules import STARTPOS
from darwin.referee import analysis

MOVES = [
    "e2e4",
    "e7e5",
    "g1f3",
    "b8c6",
    "f1c4",
    "g8f6",
    "d2d3",
    "f8c5",
    "c2c3",
    "d7d6",
    "b1d2",
    "a7a6",
]


class Account:
    async def account(self) -> dict[str, Any]:
        return {"id": "me", "perfs": {"blitz": {"rating": 1490}}}


async def ended(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch, result: str,
    moves: list[str], callback: Any,
) -> int:  # fmt: skip
    evaluated: list[list[str]] = []

    async def evaluate(settings: Settings, played: list[str], color: str) -> list[int]:
        evaluated.append(played)
        return [0] * 9 + [-300] * (len(played) - 8)  # our 5.c3 drops three pawns

    monkeypatch.setattr(game_module, "RATING_SETTLE_S", 0.0)
    monkeypatch.setattr(analysis, "evaluate", evaluate)
    await ledger.seed("0" * 40)
    await records.start_game(
        ledger, lichess_id="AbCd1234", generation_id=0, color="white", opponent="bot",
        opponent_rating=1500, opponent_title=None, rated=True, time_control="180+2",
    )  # fmt: skip
    settings = Settings(data_dir=tmp_path / "data")
    game = Game(settings, ledger, cast(LichessClient, Account()), game_id="AbCd1234",
                color="white", me="me", on_finished=callback)  # fmt: skip
    live = LiveGame("AbCd1234", 0, "white", {}, "180+2", STARTPOS, "blitz", moves=moves,
                    status="resign", result=result)  # fmt: skip
    await game._record_end(live)
    return len(evaluated)


async def test_every_finished_game_is_evaluated_and_announced(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished: list[int] = []
    assert await ended(tmp_path, ledger, monkeypatch, "win", MOVES, finished.append) == 1
    (row,) = await records.games(ledger)
    assert finished == [row.id]
    assert row.evals is not None and len(row.evals) == len(MOVES) + 1
    assert row.analysis is None  # the worst move is for losses only


async def test_a_loss_also_gets_its_worst_move(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ended(tmp_path, ledger, monkeypatch, "loss", MOVES, None)
    (row,) = await records.games(ledger)
    assert row.analysis is not None and row.analysis["move"] == "c3"


async def test_a_short_game_is_announced_without_analysis_and_a_bad_callback_is_contained(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: int) -> None:
        raise RuntimeError("listener down")

    assert await ended(tmp_path, ledger, monkeypatch, "loss", MOVES[:4], broken) == 0
    (row,) = await records.games(ledger)
    assert (row.result, row.evals, row.analysis) == ("loss", None, None)
