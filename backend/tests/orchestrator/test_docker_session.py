"""A whole agent session, end to end and free: real pi with the darwin extension, real
sandbox and referee, a scripted model in place of the LLM."""

import asyncio
import json
import socket
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from sqlalchemy import select

from darwin.config import Settings
from darwin.ledger import models as m
from darwin.ledger.store import Ledger
from darwin.orchestrator.loop import Orchestrator

from .fake_llm import make_app

pytestmark = pytest.mark.docker

AGENT_DIR = Path(__file__).resolve().parents[3] / "agent"
SCRIPT: list[dict[str, Any]] = [
    {"tool": "bash", "args": {"command": "head -c 40 CONTRACT.md && cargo build --release -q"}},
    {"tool": "perft_check", "args": {}},
    {"tool": "write", "args": {"path": "src/notes.txt", "content": "my first change\n"}},
    {
        "tool": "bash",
        "args": {"command": "echo '- seed engine is not UCI yet' >> /memory/NOTES.md"},
    },
    {"tool": "submit", "args": {"hypothesis": "Add a notes file; the engine is still not UCI."}},
    {"text": "Submitted, stopping."},
]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def genome(tmp_path: Path) -> Path:
    repo = tmp_path / "genome"
    (repo / "src").mkdir(parents=True)
    (repo / "Cargo.toml").write_text(
        '[package]\nname = "genome"\nversion = "0.1.0"\nedition = "2021"\n'
    )
    (repo / "src" / "main.rs").write_text('fn main() { println!("hello"); }\n')
    (repo / ".gitignore").write_text("/target\n")
    (repo / "CONTRACT.md").write_text("# Contract\nSpeak UCI and answer perft.\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "gen-0")
    git(repo, "tag", "gen-0")
    return repo


@pytest.fixture
async def fake_llm() -> AsyncIterator[tuple[int, list[dict[str, Any]]]]:
    seen: list[dict[str, Any]] = []
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(make_app(SCRIPT, seen), host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110  (uvicorn exposes a flag, not an event)
        await asyncio.sleep(0.05)
    yield port, seen
    server.should_exit = True
    await task


async def test_a_scripted_session_reaches_a_verdict(
    tmp_path: Path,
    genome: Path,
    ledger: Ledger,
    fake_llm: tuple[int, list[dict[str, Any]]],
    images: None,
) -> None:
    port, seen = fake_llm
    settings = Settings(
        data_dir=tmp_path / "data",
        genome_dir=genome,
        mirror_dir=tmp_path / "mirror.git",
        agent_dir=AGENT_DIR,
        tools_port=free_port(),
        llm_provider="fake",
        llm_model="scripted",
        llm_thinking="off",
    )
    home = settings.data_dir / "agent" / "pi-home"
    home.mkdir(parents=True)
    (home / "models.json").write_text(
        json.dumps(
            {
                "providers": {
                    "fake": {
                        "baseUrl": f"http://127.0.0.1:{port}/v1",
                        "api": "openai-completions",
                        "apiKey": "x",
                        "models": [
                            {
                                "id": "scripted",
                                "cost": {"input": 1, "output": 2, "cacheRead": 0, "cacheWrite": 0},
                            }
                        ],
                    }
                }
            }
        )
    )

    await Orchestrator(settings, ledger).run(max_sessions=1)

    [experiment] = await ledger.recent_experiments(5)
    async with ledger.session() as s:
        events = (await s.scalars(select(m.AgentEvent).order_by(m.AgentEvent.id))).all()
        calls = (await s.scalars(select(m.LlmCall))).all()
    trace = [(e.kind, e.payload) for e in events]
    assert experiment.status == "rejected", (experiment.error, trace)
    assert experiment.rejected_at_gate == "perft"  # it builds, but it does not speak UCI
    assert experiment.hypothesis and experiment.hypothesis.startswith("Add a notes file")
    assert experiment.diff_stat is not None and experiment.diff_stat["files"] == 2  # + Cargo.lock
    tools = [e.payload["tool"] for e in events if e.kind == "tool_call"]
    assert tools == ["bash", "perft_check", "write", "bash", "submit"]
    results = {e.payload["tool"]: e.payload for e in events if e.kind == "tool_result"}
    assert "Protocol problem" in results["perft_check"]["text"]
    assert len(calls) == len(SCRIPT) and all(c.cost_usd > 0 for c in calls)
    assert "the engine is not UCI yet" not in (genome / "CONTRACT.md").read_text()
    notes = (settings.data_dir / "agent" / "memory" / "NOTES.md").read_text()
    assert "seed engine is not UCI yet" in notes  # memory outlives the rejected experiment
    assert seen and "darwin" in json.dumps(seen[0]["messages"][0])  # our system prompt
