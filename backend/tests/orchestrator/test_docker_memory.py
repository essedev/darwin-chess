"""The memory's history, committed by a real container: what a commit records and skips."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.orchestrator import memory

pytestmark = pytest.mark.docker


def history(settings: Settings, *args: str) -> str:
    repo = memory.history_dir(settings)
    done = subprocess.run(
        ["git", "--git-dir", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    genome = tmp_path / "genome"
    genome.mkdir()
    s = Settings(data_dir=tmp_path / "data", genome_dir=genome, mirror_dir=tmp_path / "mirror.git")
    memory.memory_dir(s).mkdir(parents=True)
    return s


async def test_a_commit_per_change_and_none_when_nothing_changed(
    settings: Settings, images: None
) -> None:
    folder = memory.memory_dir(settings)
    (folder / "NOTES.md").write_text("- first\n")
    first = await memory.snapshot(settings, "startup")
    assert first is not None
    assert await memory.snapshot(settings, "exp-1: after the iteration session") is None

    (folder / "NOTES.md").write_text("- second\n- first\n")
    second = await memory.snapshot(settings, "exp-2: after the iteration session")
    assert second is not None and second != first
    assert history(settings, "log", "--format=%s", "main").splitlines() == [
        "exp-2: after the iteration session",
        "startup",
    ]
    assert history(settings, "show", "main~1:NOTES.md") == "- first\n"


async def test_records_what_the_agent_hides_and_skips_bytecode(
    settings: Settings, images: None
) -> None:
    folder = memory.memory_dir(settings)
    (folder / ".gitignore").write_text("*\n")  # the agent's own rules do not hide anything
    (folder / "match.py").write_text("print('scratch tool')\n")
    (folder / "elsewhere").symlink_to("/etc/passwd")  # kept as a link, never followed
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "match.cpython-313.pyc").write_bytes(b"\x00bytecode")
    await memory.snapshot(settings, "startup")
    files = history(settings, "ls-tree", "-r", "--name-only", "main").splitlines()
    assert sorted(files) == [".gitignore", "elsewhere", "match.py"]
    assert history(settings, "cat-file", "-p", "main:elsewhere") == "/etc/passwd"


async def test_a_commit_can_carry_a_past_date(settings: Settings, images: None) -> None:
    (memory.memory_dir(settings) / "NOTES.md").write_text("- old\n")
    when = datetime(2026, 11, 25, 12, 30, tzinfo=UTC)
    await memory.snapshot(settings, "exp-3: after the iteration session", date=when)
    assert history(settings, "log", "-1", "--format=%aI %cI", "main").split() == [
        "2026-11-25T12:30:00Z",
        "2026-11-25T12:30:00Z",
    ]
