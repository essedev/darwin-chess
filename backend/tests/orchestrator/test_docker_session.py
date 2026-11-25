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
from darwin.referee.judge import Phase, Verdict
from darwin.referee.models import Gate, GateResult

from .fake_llm import make_app

pytestmark = pytest.mark.docker

AGENT_DIR = Path(__file__).resolve().parents[3] / "agent"
SCRIPT: list[dict[str, Any]] = [
    # A commit that ends where it started: submit must refuse it, not judge it.
    {
        "tool": "bash",
        "args": {
            "command": "echo x >> CONTRACT.md && git -c user.name=a -c user.email=a@a commit -qam a"
            " && git -c user.name=a -c user.email=a@a revert --no-edit HEAD > /dev/null"
        },
    },
    {"tool": "submit", "args": {"hypothesis": "Nothing really changed in this tree."}},
    {"tool": "bash", "args": {"command": "head -c 40 CONTRACT.md && cargo build --release -q"}},
    {"tool": "perft_check", "args": {}},
    {"tool": "write", "args": {"path": "src/notes.txt", "content": "my first change\n"}},
    {
        "tool": "bash",
        "args": {"command": "echo '- seed engine is not UCI yet' >> /memory/NOTES.md"},
    },
    # The agent commits on its own: submit must still find the work (it once did not).
    {
        "tool": "bash",
        "args": {"command": "git add -A && git -c user.name=a -c user.email=a@a commit -qm mine"},
    },
    {
        "tool": "submit",
        "args": {
            "hypothesis": "Add a notes file; the engine is still not UCI.",
            "lesson_for_previous": "A stub that only prints cannot pass perft.",
        },
    },
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


def genome_gen0(repo: Path) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "gen-0"], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


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
        instance=f"test-{tmp_path.name}",  # startup cleanup must not touch anyone else
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

    # A verdict from an earlier session: this one must see it and file the lesson on it.
    gen0 = genome_gen0(genome)
    await ledger.seed(gen0)
    earlier = await ledger.start_experiment(
        kind="iteration",
        phase=Phase.GENESIS,
        base_commit=gen0,
        base_generation_id=0,
        trigger="start",
    )
    await ledger.set_submission(earlier, "Print hello", "e" * 40, {})
    await ledger.record_verdict(
        earlier,
        Verdict(False, [GateResult(Gate.PERFT, False, {"problem": "protocol"}, 1)], None, None),
    )

    await Orchestrator(settings, ledger).run(max_sessions=1)

    experiment, previous = await ledger.recent_experiments(5)
    async with ledger.session() as s:
        trace = [
            (e.kind, e.payload)
            for e in (await s.scalars(select(m.AgentEvent))).all()
            if e.kind == "tool_result"
        ]
    assert previous.id == earlier, trace
    assert previous.lesson == "A stub that only prints cannot pass perft.", trace
    assert experiment.lesson is None
    first_prompt = json.dumps(seen[0]["messages"])
    assert f"Last verdict (#{earlier}: rejected)" in first_prompt
    assert "lesson_for_previous" in first_prompt
    async with ledger.session() as s:
        events = (await s.scalars(select(m.AgentEvent).order_by(m.AgentEvent.id))).all()
        calls = (await s.scalars(select(m.LlmCall))).all()
    trace = [(e.kind, e.payload) for e in events]
    assert experiment.status == "rejected", (experiment.error, trace)
    assert experiment.rejected_at_gate == "perft"  # it builds, but it does not speak UCI
    assert experiment.hypothesis and experiment.hypothesis.startswith("Add a notes file")
    assert experiment.diff_stat is not None and experiment.diff_stat["files"] == 2  # + Cargo.lock
    tools = [e.payload["tool"] for e in events if e.kind == "tool_call"]
    assert tools == ["bash", "submit", "bash", "perft_check", "write", "bash", "bash", "submit"]
    refused = next(
        e.payload for e in events if e.kind == "tool_result" and e.payload["tool"] == "submit"
    )
    assert refused["error"] and "identical to the base" in refused["text"]
    results = {e.payload["tool"]: e.payload for e in events if e.kind == "tool_result"}
    assert "Protocol problem" in results["perft_check"]["text"]
    assert len(calls) == len(SCRIPT) and all(c.cost_usd > 0 for c in calls)
    assert "the engine is not UCI yet" not in (genome / "CONTRACT.md").read_text()
    notes = (settings.data_dir / "agent" / "memory" / "NOTES.md").read_text()
    assert "seed engine is not UCI yet" in notes  # memory outlives the rejected experiment
    assert seen and "darwin" in json.dumps(seen[0]["messages"][0])  # our system prompt
