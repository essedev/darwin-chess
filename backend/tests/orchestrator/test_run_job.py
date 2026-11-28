"""The `run_job` tool: a job needs a purpose, and its status reads back with it."""

from pathlib import Path
from typing import cast

import pytest

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.sandbox import Sandbox
from darwin.orchestrator.tools import SessionTools, ToolError
from darwin.referee.judge import Phase


async def tools(tmp_path: Path, ledger: Ledger) -> tuple[SessionTools, int]:
    await ledger.seed("0" * 40)
    experiment = await ledger.start_experiment(
        kind="iteration", phase=Phase.EVOLUTION, base_commit="0" * 40,
        base_generation_id=0, trigger="start",
    )  # fmt: skip
    settings = Settings(data_dir=tmp_path)

    async def ignore(_job_id: int) -> None:
        return None

    jobs = Jobs(settings, ledger, on_done=ignore)
    session = SessionTools(settings, ledger, jobs, cast(Sandbox, None), experiment, "0" * 40, None)
    return session, experiment


@pytest.mark.parametrize("purpose", [None, "", "   "])
async def test_a_job_without_a_purpose_is_refused(
    tmp_path: Path, ledger: Ledger, purpose: str | None
) -> None:
    session, _ = await tools(tmp_path, ledger)
    with pytest.raises(ToolError, match="purpose"):
        await session.run_job({"action": "start", "command": "true", "purpose": purpose})
    assert await ledger.jobs() == []


async def test_the_status_names_each_job_by_its_purpose(tmp_path: Path, ledger: Ledger) -> None:
    session, experiment = await tools(tmp_path, ledger)
    job = await ledger.start_job(experiment, "python3 selfplay.py", "Self-play games", 2, 2)
    await ledger.finish_job(job, "killed", None, "time limit\n")
    status = await session.run_job({"action": "status"})
    assert f"job {job}: killed (exit None) Self-play games: `python3 selfplay.py`" in status
