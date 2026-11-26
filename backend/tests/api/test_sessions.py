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
