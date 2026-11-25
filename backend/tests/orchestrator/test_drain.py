"""Draining core before a restart: no new session or Lichess game, then the answer file.
No container and no model: the session runner must never be reached."""

import asyncio
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import loop as loop_module
from darwin.orchestrator.loop import Orchestrator
from darwin.referee.docker import only_going


class FakeBot:
    def __init__(self) -> None:
        self.drained = False
        self.playing = True

    def drain(self) -> None:
        self.drained = True

    def busy(self) -> bool:
        return self.playing


@pytest.fixture
async def orchestrator(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> Orchestrator:
    monkeypatch.setattr(loop_module, "CHECK_EVERY_S", 0.05)
    await ledger.seed("0" * 40)
    settings = Settings(data_dir=tmp_path, llm_provider="anthropic", daily_budget_usd=0.0)
    orch = Orchestrator(settings, ledger)

    async def no_session(**_: object) -> None:
        raise AssertionError("a session started while draining")

    monkeypatch.setattr(orch.sessions, "run", no_session)
    return orch


async def test_the_request_stops_the_agent_and_the_bot(orchestrator: Orchestrator) -> None:
    bot = FakeBot()
    watching = asyncio.create_task(orchestrator._watch_drain(bot))  # type: ignore[arg-type]
    # The budget is zero: without a drain the loop would wait for money, not return.
    looping = asyncio.create_task(orchestrator.agent_loop(None))
    await asyncio.sleep(0.1)
    assert not looping.done()
    orchestrator.drain.dir.mkdir(parents=True)
    orchestrator.drain.request.touch()
    await asyncio.wait_for(looping, 2)
    await asyncio.wait_for(watching, 2)
    assert orchestrator.draining.is_set() and bot.drained


async def test_drained_only_after_the_lichess_game(orchestrator: Orchestrator) -> None:
    bot = FakeBot()
    settling = asyncio.create_task(orchestrator.settle(bot))  # type: ignore[arg-type]
    await asyncio.sleep(0.2)
    assert not orchestrator.drain.done.exists()  # the game is still on
    bot.playing = False
    await asyncio.wait_for(settling, 2)
    assert orchestrator.drain.done.exists()


async def test_a_new_process_ignores_an_old_request(orchestrator: Orchestrator) -> None:
    orchestrator.drain.mark_done()
    orchestrator.drain.request.touch()
    orchestrator.drain.reset()
    assert not orchestrator.drain.requested() and not orchestrator.drain.done.exists()


@pytest.mark.parametrize(
    ("stderr", "gone"),
    [
        ("Error response from daemon: removal of container a0f7 is already in progress", True),
        ("Error response from daemon: No such container: a0f7\n", True),
        ("Error response from daemon: No such container: a\nError: permission denied", False),
        ("", False),
    ],
)
def test_containers_already_going_are_not_a_failure(stderr: str, gone: bool) -> None:
    assert only_going(stderr) is gone
