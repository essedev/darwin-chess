"""A whole Lichess game against a fake server: the engine plays in a real container, the
game lands in the ledger, the loss is analysed by real Stockfish, the live file follows."""

import asyncio
import json
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from darwin.config import Settings
from darwin.ledger import models as m
from darwin.ledger.store import Ledger
from darwin.lichess import game
from darwin.referee import docker, engines
from darwin.referee.models import EngineSpec

from .conftest import bot_settings, running_bot
from .fake_lichess import GAME_ID, FakeLichess

pytestmark = pytest.mark.docker


@pytest.fixture(autouse=True)
def run_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Tags this test's containers, so the leftover check ignores anyone else's."""
    prefix = f"t{uuid.uuid4().hex[:6]}"
    monkeypatch.setattr(docker, "new_run_id", lambda: prefix + uuid.uuid4().hex[:6])
    monkeypatch.setattr(game, "RATING_SETTLE_S", 0.0)
    return prefix


def leftover_containers(prefix: str) -> list[str]:
    listed = subprocess.run(
        ["docker", "ps", "-a", "--filter", "label=darwin.run", "--format",
         '{{.Label "darwin.run"}}'],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [label for label in listed.stdout.split() if label.startswith(prefix)]


async def finished_row(ledger: Ledger) -> m.LichessGame | None:
    async with ledger.session() as s:
        return await s.scalar(select(m.LichessGame).where(m.LichessGame.lichess_id == GAME_ID))


async def test_a_lost_game_is_recorded_and_analysed(
    tmp_path: Path,
    fake: FakeLichess,
    lichess_url: str,
    ledger: Ledger,
    images: None,
    run_prefix: str,
) -> None:
    await ledger.seed("0" * 40)
    async with ledger.session() as s:
        s.add(m.Generation(id=1, commit_sha="1" * 40))
    settings: Settings = bot_settings(tmp_path, lichess_url)

    async def random_champion() -> tuple[int, EngineSpec] | None:
        return 1, engines.random_player(settings)

    row: m.LichessGame | None = None

    async def analysed() -> bool:
        nonlocal row
        row = await finished_row(ledger)
        return row is not None and row.analysis is not None

    fake.start_game()
    async with running_bot(settings, ledger, random_champion):
        async with asyncio.timeout(180):  # the game, then Stockfish over each position
            while not await analysed():  # noqa: ASYNC110  (polls the ledger)
                await asyncio.sleep(0.2)

    assert row is not None and row.analysis is not None
    assert fake.refused_moves == []
    assert (row.generation_id, row.color, row.opponent) == (1, "white", "OppBot")
    assert (row.opponent_rating, row.opponent_title, row.rated) == (1600, "BOT", True)
    assert row.time_control == "180+2"
    assert (row.status, row.result, row.rating_after) == ("mate", "loss", 1500)
    moves = row.moves.split()
    assert moves == [move.uci() for move in fake.board.move_stack]
    assert len(moves) == fake.game_plies
    worst = row.analysis
    assert worst["drop_cp"] == worst["eval_before_cp"] - worst["eval_after_cp"]
    assert {"move_number", "move", "fen_before"} <= worst.keys()

    live = json.loads((settings.data_dir / "lichess" / "current.json").read_text())
    assert live["game_id"] == GAME_ID and live["url"] == f"https://lichess.org/{GAME_ID}"
    assert (live["status"], live["result"], live["generation"]) == ("mate", "loss", 1)
    assert live["moves"] == moves
    assert live["opponent"] == {"name": "OppBot", "rating": 1600, "title": "BOT"}
    assert (live["color"], live["time_control"], live["initial_fen"]) == (
        "white", "180+2", "startpos",
    )  # fmt: skip
    assert live["wtime"] == live["btime"] == 180_000
    assert not (settings.data_dir / "lichess" / "current.json.tmp").exists()
    assert leftover_containers(run_prefix) == []
