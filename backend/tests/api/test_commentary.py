"""Commentary in the API: Italian next to the agent's English, and the match list."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.config import get_settings
from darwin.ledger import commentary, lichess
from darwin.ledger.commentary import Subject
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase, Verdict
from darwin.referee.match import MatchResult
from darwin.referee.models import GameRecord, Gate, GateResult, Termination
from darwin.referee.sprt import SprtVerdict


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


def match(opponent: str, wins: int) -> MatchResult:
    games = [GameRecord("candidate", opponent, "1-0", Termination.CHECKMATE, "fen", "pgn")] * wins
    return MatchResult(games, [0, 0, 0, 0, 1], 191.0, 80.0, 3.1, SprtVerdict.H1, opponent, "2+0")


async def note(ledger: Ledger, kind: str, subject_id: int, text_it: str, text_en: str) -> None:
    await commentary.add(
        ledger, Subject(kind, subject_id), text_it=text_it, text_en=text_en,
        model="claude-haiku-5-5", input_tokens=10, output_tokens=5, cost_usd=0.0001,
    )  # fmt: skip


def seed(ledger_url: str) -> None:
    async def go() -> None:
        ledger = Ledger(ledger_url)
        await ledger.seed("0" * 40)
        first = await ledger.start_experiment(kind="iteration", phase=Phase.FIRST_STEPS,
                                              base_commit="0" * 40, base_generation_id=0,
                                              trigger="start")  # fmt: skip
        await ledger.set_submission(first, "Add a search", "1" * 40, {"files": 4})
        gate = GateResult(Gate.MATCH, True, {"games": 1}, 5)
        await ledger.record_verdict(first, Verdict(True, [gate], None, match("random", 1)))
        await ledger.set_lesson(first, "Search pays.")
        second = await ledger.start_experiment(kind="iteration", phase=Phase.EVOLUTION,
                                               base_commit="1" * 40, base_generation_id=1,
                                               trigger="verdict")  # fmt: skip
        await ledger.set_submission(second, "Tweak eval", "2" * 40, {"files": 1})
        gate = GateResult(Gate.MATCH, False, {"games": 2}, 5)
        await ledger.record_verdict(second, Verdict(False, [gate], None, match("champion", 2)))
        await note(ledger, "hypothesis", first, "Aggiungi una ricerca", "Add a search")
        await note(ledger, "lesson", first, "La ricerca paga.", "Search pays.")
        await note(ledger, "match", 1, "Ha battuto il giocatore casuale.", "It beat random.")
        for n, lichess_id in enumerate(("g1", "g2")):
            await lichess.start_game(ledger, lichess_id=lichess_id, generation_id=1,
                                     color="white", opponent="bot", opponent_rating=1400,
                                     opponent_title="BOT", rated=True,
                                     time_control="180+2")  # fmt: skip
            game_id = await lichess.finish_game(ledger, lichess_id, status="mate",
                                                result="win", moves="e2e4",
                                                rating_after=1510 + n)  # fmt: skip
        await note(ledger, "lichess_game", game_id, "Vinta.", "Won.")
        await ledger.close()

    asyncio.run(go())


def test_matches_newest_first_with_hypothesis_and_commentary(
    client: TestClient, ledger_url: str
) -> None:
    assert client.get("/api/matches").json() == []
    seed(ledger_url)
    newest, oldest = client.get("/api/matches").json()
    assert oldest == {
        "id": 1,
        "experiment_id": 1,
        "kind": "sprt",
        "opponent": "random",
        "wins": 1,
        "draws": 0,
        "losses": 0,
        "pentanomial": [0, 0, 0, 0, 1],
        "elo": 191.0,
        "elo_error": 80.0,
        "verdict": "h1",
        "time_control": "2+0",
        "finished_at": oldest["finished_at"],
        "hypothesis_en": "Add a search",
        "hypothesis_it": "Aggiungi una ricerca",
        "commentary": {"it": "Ha battuto il giocatore casuale.", "en": "It beat random."},
    }
    assert oldest["finished_at"] is not None
    assert (newest["id"], newest["opponent"], newest["wins"]) == (2, "champion", 2)
    assert (newest["hypothesis_en"], newest["hypothesis_it"], newest["commentary"]) == (
        "Tweak eval", None, None,
    )  # fmt: skip
    assert [m["id"] for m in client.get("/api/matches", params={"limit": 1}).json()] == [2]
    for bad in ({"limit": 0}, {"limit": 51}, {"limit": "x"}):
        assert client.get("/api/matches", params=bad).status_code == 400


def test_italian_next_to_the_agents_english(client: TestClient, ledger_url: str) -> None:
    seed(ledger_url)
    items = client.get("/api/experiments").json()["items"]
    assert [(e["hypothesis"], e["hypothesis_it"], e["lesson"], e["lesson_it"]) for e in items] == [
        ("Tweak eval", None, None, None),
        ("Add a search", "Aggiungi una ricerca", "Search pays.", "La ricerca paga."),
    ]
    gen1, gen0 = client.get("/api/generations/detail").json()
    assert (gen1["hypothesis_it"], gen1["lesson_it"]) == (
        "Aggiungi una ricerca",
        "La ricerca paga.",
    )
    assert (gen0["hypothesis_it"], gen0["lesson_it"]) == (None, None)
    overview = client.get("/api/overview").json()
    assert (overview["current"]["hypothesis"], overview["current"]["hypothesis_it"]) == (
        "Tweak eval", None,
    )  # fmt: skip
    assert overview["previous"]["hypothesis_it"] == "Aggiungi una ricerca"


def test_lichess_games_carry_their_commentary(client: TestClient, ledger_url: str) -> None:
    seed(ledger_url)
    newest, oldest = client.get("/api/lichess").json()["recent"]
    assert newest["lichess_id"] == "g2" and newest["commentary"] == {"it": "Vinta.", "en": "Won."}
    assert oldest["commentary"] is None
