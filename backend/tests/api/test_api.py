import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.api.live import read_live_game
from darwin.config import get_settings
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase, Verdict
from darwin.referee.models import Gate, GateResult


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


def seed(ledger_url: str) -> None:
    async def go() -> None:
        ledger = Ledger(ledger_url)
        await ledger.seed("0" * 40)
        exp = await ledger.start_experiment(
            kind="iteration",
            phase=Phase.GENESIS,
            base_commit="0" * 40,
            base_generation_id=0,
            trigger="start",
        )
        await ledger.set_submission(exp, "Write the move generator", "a" * 40, {"files": 3})
        await ledger.add_event(exp, "thought", {"text": "Bitboards first."})
        await ledger.record_verdict(
            exp,
            Verdict(
                False, [GateResult(Gate.PERFT, False, {"problem": "wrong_count"}, 9)], None, None
            ),
        )
        await ledger.close()

    asyncio.run(go())


def test_overview_before_the_seed_says_not_ready(client: TestClient) -> None:
    assert client.get("/api/overview").json() == {"ready": False}


def test_overview_tells_the_story(client: TestClient, ledger_url: str) -> None:
    seed(ledger_url)
    body = client.get("/api/overview").json()
    assert body["phase"] == "genesis"
    assert body["champion"]["id"] == 0
    assert body["current"]["hypothesis"] == "Write the move generator"
    assert body["current"]["gates"] == [
        {"gate": "perft", "passed": False, "detail": {"problem": "wrong_count"}}
    ]
    assert body["experiments"]["total"] == 1
    assert body["events"][-1]["payload"] == {"text": "Bitboards first."}


def test_live_game_follows_the_newest_running_game(tmp_path: Path) -> None:
    match = tmp_path / "abc"
    match.mkdir()
    lines = [
        {
            "event": "game_started",
            "game": 1,
            "white": "candidate",
            "black": "random",
            "start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        },
        {"event": "move", "game": 1, "move": "e2e4"},
        {
            "event": "game_started",
            "game": 2,
            "white": "random",
            "black": "candidate",
            "start_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        },
        {"event": "move", "game": 1, "move": "e7e5"},
        {"event": "game_finished", "game": 2, "result": "1-0", "termination": "illegal_move"},
    ]
    (match / "events.ndjson").write_text("\n".join(json.dumps(x) for x in lines) + '\n{"event"')
    game = read_live_game(tmp_path)
    assert game is not None
    assert (game["game"], game["san"], game["last_move"]) == (1, ["e4", "e5"], "e7e5")
    assert game["result"] is None
    assert game["tally"]["candidate"] == {"wins": 0, "draws": 0, "losses": 1}
