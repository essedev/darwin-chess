import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.lichess.bot import EngineFor, LichessBot
from darwin.lichess.client import LichessClient

from .fake_lichess import FakeLichess, serve


@pytest.fixture
def fake() -> FakeLichess:
    return FakeLichess()


@pytest.fixture
async def lichess_url(fake: FakeLichess) -> AsyncIterator[str]:
    server, task, url = await serve(fake)
    yield url
    server.should_exit = True
    await task


def bot_settings(tmp_path: Path, url: str, challenge_every_s: float = 3600.0) -> Settings:
    return Settings(data_dir=tmp_path / "data", genome_dir=tmp_path / "genome",
                    mirror_dir=tmp_path / "mirror.git", lichess_enabled=True,
                    lichess_url=url, lichess_challenge_every_s=challenge_every_s)  # fmt: skip


@contextlib.asynccontextmanager
async def running_bot(
    settings: Settings, ledger: Ledger, engine_for: EngineFor
) -> AsyncIterator[LichessBot]:
    """The bot against the fake server, cancelled and closed however the test ends."""
    client = LichessClient(settings.lichess_url, "test-token")
    bot = LichessBot(settings, ledger, client, engine_for)
    task = asyncio.create_task(bot.run())
    try:
        yield bot
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await client.close()


async def until(condition: Callable[[], bool], timeout_s: float) -> None:
    async with asyncio.timeout(timeout_s):
        while not condition():  # noqa: ASYNC110  (polls state the bot changes)
            await asyncio.sleep(0.05)
