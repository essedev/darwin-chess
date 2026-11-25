import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.api.live import Follower, LiveGame, read_live_game
from darwin.config import get_settings
from darwin.ledger import commentary, lichess
from darwin.ledger import models as m
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
        thought = await ledger.add_event(exp, "thought", {"text": "Bitboards first."})
        await commentary.add(
            ledger, commentary.Subject(commentary.THOUGHT, thought), text_it="Prima le bitboard.",
            text_en="Bitboards first.", model="m", input_tokens=1, output_tokens=1, cost_usd=0.0,
        )  # fmt: skip
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
    assert body["events"][-1]["text_it"] == "Prima le bitboard."


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
    assert game["running"] == 1


def test_lichess_without_games_is_empty(client: TestClient) -> None:
    assert client.get("/api/lichess").json() == {
        "live": None,
        "profile_url": "https://lichess.org/@/darwin-chess-bot/all",
        "recent": [],
        "performance": {},
    }


def test_lichess_shows_the_live_game_and_the_finished_ones(
    client: TestClient, ledger_url: str, tmp_path: Path
) -> None:
    async def go() -> None:
        ledger = Ledger(ledger_url)
        await ledger.seed("0" * 40)
        await lichess.start_game(
            ledger,
            lichess_id="AbCd1234",
            generation_id=0,
            color="black",
            opponent="maia1",
            opponent_rating=1500,
            opponent_title="BOT",
            rated=True,
            time_control="180+2",
        )
        await lichess.finish_game(
            ledger, "AbCd1234", status="mate", result="win", moves="e2e4", rating_after=1520
        )
        await ledger.close()

    asyncio.run(go())
    current = tmp_path / "data" / "lichess" / "current.json"
    current.parent.mkdir(parents=True)
    state = {
        "game_id": "XyZ98765",
        "url": "https://lichess.org/XyZ98765",
        "generation": 0,
        "color": "white",
        "opponent": {"name": "maia5", "rating": 1600, "title": "BOT"},
        "time_control": "180+2",
        "initial_fen": "startpos",
        "moves": ["e2e4", "e7e5", "g1f3"],
        "wtime": 170000,
        "btime": 175000,
        "status": "started",
        "result": None,
        "updated_at": "2026-11-25T10:00:00+00:00",
    }
    current.write_text(json.dumps(state))

    body = client.get("/api/lichess").json()
    live = body["live"]
    assert live["game_id"] == "XyZ98765"
    assert live["opponent"] == {"name": "maia5", "rating": 1600, "title": "BOT"}
    assert live["san"] == ["e4", "e5", "Nf3"]
    assert live["last_move"] == "g1f3"
    assert live["fen"].startswith("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b")
    assert body["recent"] == [
        {
            "lichess_id": "AbCd1234",
            "url": "https://lichess.org/AbCd1234",
            "opponent": "maia1",
            "opponent_rating": 1500,
            "opponent_title": "BOT",
            "color": "black",
            "result": "win",
            "status": "mate",
            "generation_id": 0,
            "time_control": "180+2",
            "finished_at": body["recent"][0]["finished_at"],
            "commentary": None,
        }
    ]
    assert body["performance"] == {
        "0": {"games": 1, "wins": 1, "draws": 0, "losses": 0, "performance": 1900}
    }

    current.write_text(json.dumps({**state, "status": "mate", "result": "win"}))
    assert client.get("/api/lichess").json()["live"] is None


def test_overview_lists_the_running_job_and_the_last_finished(
    client: TestClient, ledger_url: str
) -> None:
    seed(ledger_url)

    async def go() -> None:
        ledger = Ledger(ledger_url)
        async with ledger.session() as s:
            s.add(m.Job(experiment_id=1, command="selfplay --games 100", cpus=2, max_hours=4))
            s.add(
                m.Job(
                    experiment_id=1,
                    command="train",
                    cpus=2,
                    max_hours=1,
                    status="failed",
                    exit_code=2,
                    finished_at=m.utcnow(),
                )
            )
        await ledger.close()

    asyncio.run(go())
    jobs = client.get("/api/overview").json()["jobs"]
    assert [(j["command"], j["max_hours"]) for j in jobs["running"]] == [
        ("selfplay --games 100", 4)
    ]
    assert (jobs["last_finished"]["command"], jobs["last_finished"]["exit_code"]) == ("train", 2)


def test_the_board_follows_one_game_to_its_end_then_holds_it() -> None:
    now = [0.0]
    follower = Follower(hold_s=3.0, clock=lambda: now[0])
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    first, second = (
        LiveGame("m1", 1, "candidate", "champion", fen),
        LiveGame("m1", 2, "champion", "candidate", fen),
    )
    assert follower.pick([first, second]) is first
    third = LiveGame("m1", 3, "candidate", "champion", fen)
    assert follower.pick([first, second, third]) is first  # a newer game does not steal the board
    first.result = "1-0"
    assert follower.pick([first, second, third]) is first  # the final position stays a moment
    now[0] = 2.9
    assert follower.pick([first, second, third]) is first
    now[0] = 3.1
    assert follower.pick([first, second, third]) is second  # then the oldest still running
    batch = LiveGame("m2", 1, "candidate", "champion", fen)
    assert follower.pick([batch]) is batch  # a new batch: its own games
