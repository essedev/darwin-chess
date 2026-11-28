"""The session page's endpoint: one experiment with its events, new and old payloads alike,
against a real ledger."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.config import get_settings
from darwin.ledger import commentary, sessions
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase, Verdict
from darwin.referee.models import Gate, GateResult

# A row written before tool arguments became JSON: the repr of the dict, as session.py stored it.
LEGACY_ARGS = "{'command': 'cd /genome && cargo build --release 2>&1 | tail -3', 'timeout': 300}"


@pytest.fixture
def client(
    ledger_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("DARWIN_LEDGER_URL", ledger_url)
    monkeypatch.setenv("DARWIN_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def seed(ledger_url: str) -> tuple[int, int, int]:
    """An old rejected session, a reflection, and a session still running."""

    async def go() -> tuple[int, int, int]:
        ledger = Ledger(ledger_url)
        await ledger.seed("0" * 40)

        async def start(kind: str) -> int:
            return await ledger.start_experiment(kind=kind, phase=Phase.EVOLUTION,
                                                 base_commit="0" * 40, base_generation_id=0,
                                                 trigger="start")  # fmt: skip

        old = await start("iteration")
        await ledger.add_event(old, "status", {"state": "started"})
        await ledger.add_event(old, "tool_call", {"tool": "bash", "args": LEGACY_ARGS})
        await ledger.add_event(old, "tool_result",
                               {"tool": "bash", "error": False, "text": "Finished"})  # fmt: skip
        thought = await ledger.add_event(old, "thought", {"text": "It builds."})
        await commentary.add(ledger, commentary.Subject(commentary.THOUGHT, thought),
                             text_it="Compila.", text_en="It builds.", model="m",
                             input_tokens=1, output_tokens=1, cost_usd=0.0)  # fmt: skip
        await ledger.add_llm_call(old, "m", input_tokens=1, cached_tokens=0, output_tokens=1,
                                  cost_usd=0.004)  # fmt: skip
        await ledger.set_submission(old, "Null-move pruning", "a" * 40, {"files": 1})
        failed = GateResult(Gate.PERFT, False, {"problem": "wrong_count", "move": "e2e4"}, 9)
        await ledger.record_verdict(old, Verdict(False, [failed], None, None))
        reflection = await start("reflection")
        await ledger.finish_experiment(reflection, "reflected")
        running = await start("iteration")
        await ledger.add_event(running, "reasoning", {"text": "Try quiescence.", "cut": False})
        await ledger.add_event(running, "tool_call", {"tool": "read", "call_id": "toolu_1",
                                                      "args": {"path": "src/main.rs"},
                                                      "cut": False})  # fmt: skip
        await ledger.close()
        return old, reflection, running

    return asyncio.run(go())


def test_an_old_session_with_its_legacy_payloads_and_its_verdict(
    client: TestClient, ledger_url: str
) -> None:
    old, reflection, _ = seed(ledger_url)
    body = client.get(f"/api/sessions/{old}").json()
    assert (body["id"], body["kind"], body["status"]) == (old, "iteration", "rejected")
    assert (body["previous"], body["next"]) == (None, reflection)
    assert body["rejected_at_gate"] == "perft" and body["generation_id"] is None
    assert body["gates"] == [{"gate": "perft", "passed": False,
                              "detail": {"problem": "wrong_count", "move": "e2e4"}}]  # fmt: skip
    assert body["cost_usd"] == pytest.approx(0.004) and body["finished_at"] is not None
    assert body["truncated"] is False
    assert body["limits"] == {"minutes": 40, "tool_calls": 80}
    kinds = [e["kind"] for e in body["events"]]
    assert kinds == ["status", "tool_call", "tool_result", "thought"]
    call = body["events"][1]
    assert call["payload"]["args"] == LEGACY_ARGS  # handed over as stored
    assert body["events"][3]["text_it"] == "Compila."


def test_a_running_session_and_a_reflection(client: TestClient, ledger_url: str) -> None:
    old, reflection, running = seed(ledger_url)
    body = client.get(f"/api/sessions/{running}").json()
    assert (body["status"], body["finished_at"], body["next"]) == ("running", None, None)
    assert body["previous"] == reflection
    reasoning, call = body["events"]
    assert (reasoning["kind"], reasoning["text_it"]) == ("reasoning", None)  # never translated
    assert call["payload"]["args"] == {"path": "src/main.rs"}
    assert call["payload"]["call_id"] == "toolu_1"
    quiet = client.get(f"/api/sessions/{reflection}").json()
    assert (quiet["kind"], quiet["events"], quiet["previous"]) == ("reflection", [], old)


def test_unknown_and_bad_ids(client: TestClient, ledger_url: str) -> None:
    seed(ledger_url)
    assert client.get("/api/sessions/999").status_code == 404
    for bad in ("0", "-1", "x"):
        assert client.get(f"/api/sessions/{bad}").status_code == 400


def test_the_events_are_capped(
    client: TestClient, ledger_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, running = seed(ledger_url)
    monkeypatch.setattr(sessions, "MAX_EVENTS", 1)
    body = client.get(f"/api/sessions/{running}").json()
    assert (len(body["events"]), body["truncated"]) == (1, True)


TRACEBACK = """Traceback (most recent call last):
  File "/job/src/tools/selfplay.py", line 10, in <module>
FileNotFoundError: [Errno 2] No such file or directory: 'target/release/genome'
"""


@pytest.mark.parametrize(
    ("status", "log_tail", "reason"),
    [("failed", TRACEBACK, "FileNotFoundError: [Errno 2] No such file or directory: "
      "'target/release/genome'"),
     ("killed", "time limit\nplayed 300 games\n", "time limit"),
     ("failed", "", None),
     ("done", "wrote 300 games\n", None)],
)  # fmt: skip
def test_a_session_shows_the_jobs_it_started_and_how_they_ended(
    client: TestClient, ledger_url: str, status: str, log_tail: str, reason: str | None
) -> None:
    old, reflection, _ = seed(ledger_url)

    async def go() -> None:
        ledger = Ledger(ledger_url)
        job = await ledger.start_job(old, "python3 tools/selfplay.py", "Self-play games", 2, 2)
        await ledger.finish_job(job, status, 1 if status == "failed" else None, log_tail)
        await ledger.close()

    asyncio.run(go())
    [job] = client.get(f"/api/sessions/{old}").json()["jobs"]
    assert (job["purpose"], job["status"], job["reason"]) == ("Self-play games", status, reason)
    assert job["command"] == "python3 tools/selfplay.py" and job["finished_at"] is not None
    assert client.get(f"/api/sessions/{reflection}").json()["jobs"] == []


def test_sessions_that_read_a_job_and_the_job_that_was_read(
    client: TestClient, ledger_url: str
) -> None:
    old, reflection, running = seed(ledger_url)

    async def go() -> int:
        ledger = Ledger(ledger_url)
        job = await ledger.start_job(old, "python3 selfplay.py", "Self-play games", 2, 2)
        await ledger.finish_job(job, "done", 0, "ok\n")
        # The session that started it checks on it: that is not reading someone else's job.
        await ledger.add_event(
            old, "tool_call", {"tool": "bash", "args": {"command": f"ls /jobs/{job}/out"}}
        )
        await ledger.add_event(
            running, "tool_call", {"tool": "read", "args": {"path": f"/jobs/{job}/out/g.txt"}}
        )
        await ledger.add_event(
            reflection, "tool_call", {"tool": "bash", "args": {"command": "ls /jobs/99/out"}}
        )
        await ledger.close()
        return job

    job = asyncio.run(go())  # fmt: skip
    started = client.get(f"/api/sessions/{old}").json()
    assert started["jobs"][0]["read_by"] == [running] and started["jobs_read"] == []
    reader = client.get(f"/api/sessions/{running}").json()
    assert reader["jobs_read"] == [
        {
            "id": job,
            "purpose": "Self-play games",
            "command": "python3 selfplay.py",
            "experiment_id": old,
        }
    ]
    assert client.get(f"/api/sessions/{reflection}").json()["jobs_read"] == []  # no job 99
    rows = {e["id"]: e for e in client.get("/api/experiments").json()["items"]}
    assert (rows[old]["jobs_started"], rows[old]["jobs_read"]) == ([job], [])
    assert (rows[running]["jobs_started"], rows[running]["jobs_read"]) == ([], [job])
