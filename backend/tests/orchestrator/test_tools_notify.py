"""`submit` tells the router's listener of the texts it records (for the commentary)."""

from pathlib import Path
from typing import Any, cast

import pytest

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import sandbox
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.sandbox import Sandbox
from darwin.orchestrator.tools import SessionTools, ToolRouter
from darwin.referee.judge import Phase


class FakeSandbox:
    async def commit_all(self, message: str, base: str) -> str:
        return "c" * 40

    async def diff_stat(self, base: str, head: str) -> dict[str, Any]:
        return {"files": 1}


async def archive(settings: Settings, sha: str, name: str) -> None:
    return None


async def experiment(ledger: Ledger) -> int:
    return await ledger.start_experiment(
        kind="iteration", phase=Phase.GENESIS, base_commit="0" * 40,
        base_generation_id=0, trigger="start",
    )  # fmt: skip


async def test_submit_announces_the_hypothesis_and_the_lesson(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sandbox, "archive", archive)
    await ledger.seed("0" * 40)
    previous, current = await experiment(ledger), await experiment(ledger)
    heard: list[tuple[str, int]] = []
    router = ToolRouter(notify=lambda kind, exp_id: heard.append((kind, exp_id)))
    session = SessionTools(Settings(data_dir=tmp_path), ledger, cast(Jobs, None),
                           cast(Sandbox, FakeSandbox()), current, "0" * 40, previous)  # fmt: skip
    router.register(session)
    await session.call(
        "submit", {"hypothesis": "Search captures first", "lesson_for_previous": "It helped."}
    )
    assert heard == [("hypothesis", current), ("lesson", previous)]


async def test_a_failing_listener_does_not_break_submit(
    tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sandbox, "archive", archive)
    await ledger.seed("0" * 40)
    current = await experiment(ledger)

    def broken(kind: str, experiment_id: int) -> None:
        raise RuntimeError("listener down")

    session = SessionTools(Settings(data_dir=tmp_path), ledger, cast(Jobs, None),
                           cast(Sandbox, FakeSandbox()), current, "0" * 40, None,
                           notify=broken)  # fmt: skip
    text = await session.call("submit", {"hypothesis": "Search captures first"})
    assert text.startswith("Submitted cccccccccccc")
    assert (await ledger.experiment(current)).hypothesis == "Search captures first"
