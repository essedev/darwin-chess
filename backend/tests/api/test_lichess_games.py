"""The history of the bot's Lichess games: the list page and one game move by move."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.config import get_settings
from darwin.ledger import commentary, lichess, lichess_history
from darwin.ledger.commentary import Subject
from darwin.ledger.store import Ledger

ITALIAN = "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6"
# From the bot's side (Black): its second move gives almost four pawns away.
ITALIAN_EVALS = [0, -20, -20, -20, -400, -380, -400]


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


async def game(
    ledger: Ledger,
    lichess_id: str,
    *,
    result: str,
    moves: str,
    color: str = "black",
    rated: bool = True,
    evals: list[int] | None = None,
    opponent: str = "maia1",
    title: str | None = "BOT",
    time_control: str = "180+2",
) -> int:
    await lichess.start_game(
        ledger, lichess_id=lichess_id, generation_id=0, color=color, opponent=opponent,
        opponent_rating=1500, opponent_title=title, rated=rated, time_control=time_control,
    )  # fmt: skip
    row_id = await lichess.finish_game(
        ledger, lichess_id, status="resign", result=result, moves=moves, rating_after=1520
    )
    if evals is not None:
        await lichess.set_evals(ledger, row_id, evals)
    return row_id


@pytest.fixture
def seeded(ledger_url: str) -> None:
    """Oldest first: an analysed blitz loss to a bot with a commentary, an aborted game, a
    short casual rapid win over a human that Stockfish never evaluated, a rated bullet draw
    with another bot, and a game still being played."""

    async def go() -> None:
        ledger = Ledger(ledger_url)
        await ledger.seed("0" * 40)
        loss = await game(ledger, "Loss0001", result="loss", moves=ITALIAN, evals=ITALIAN_EVALS)
        await commentary.add(
            ledger, Subject(commentary.LICHESS_GAME, loss), text_it="Persa.", text_en="Lost.",
            model="claude-haiku-5-5", input_tokens=1, output_tokens=1, cost_usd=0.0,
        )  # fmt: skip
        await game(ledger, "Abort001", result="aborted", moves="")
        await game(
            ledger,
            "Win00001",
            result="win",
            moves="e2e4 e7e5",
            color="white",
            rated=False,
            opponent="Some_Human%",
            title=None,
            time_control="480+0",
        )
        await game(ledger, "Draw0001", result="draw", moves="d2d4 d7d5", opponent="MaiaBot",
                   time_control="60+0")  # fmt: skip
        await lichess.start_game(
            ledger, lichess_id="Live0001", generation_id=0, color="white", opponent="maia5",
            opponent_rating=1600, opponent_title="BOT", rated=True, time_control="180+2",
        )  # fmt: skip
        await ledger.close()

    asyncio.run(go())


def test_the_list_holds_finished_games_newest_first(client: TestClient, seeded: None) -> None:
    body = client.get("/api/lichess/games").json()
    assert [g["lichess_id"] for g in body["items"]] == ["Draw0001", "Win00001", "Loss0001"]
    assert body["next_before_id"] is None
    assert body["counts"] == {"win": 1, "draw": 1, "loss": 1, "total": 3}
    assert body["generations"] == [{"id": 0, "games": 3}]
    assert body["speeds"] == [
        {"id": "bullet", "games": 1},
        {"id": "blitz", "games": 1},
        {"id": "rapid", "games": 1},
    ]
    assert [g["speed"] for g in body["items"]] == ["bullet", "rapid", "blitz"]
    # The casual win is left out of the performance; the aborted game was never played.
    assert body["performance"]["0"]["games"] == 2
    assert body["profile_url"] == "https://lichess.org/@/darwin-chess-bot/all"
    loss = body["items"][2]
    assert loss["url"] == "https://lichess.org/Loss0001"
    assert loss["plies"] == 6
    assert loss["ours"] == {"blunder": 1, "mistake": 0, "inaccuracy": 0, "acpl": 133}
    assert len(loss["curve"]) == 7
    assert loss["commentary"] == {"it": "Persa.", "en": "Lost."}
    win = body["items"][1]
    assert win["curve"] is None and win["ours"] is None and win["commentary"] is None


def test_the_list_filters_and_pages(client: TestClient, seeded: None) -> None:
    first = client.get("/api/lichess/games", params={"limit": 2}).json()
    assert [g["lichess_id"] for g in first["items"]] == ["Draw0001", "Win00001"]
    rest = client.get(
        "/api/lichess/games", params={"limit": 2, "before_id": first["next_before_id"]}
    ).json()
    assert [g["lichess_id"] for g in rest["items"]] == ["Loss0001"]
    assert rest["next_before_id"] is None

    losses = client.get("/api/lichess/games", params={"result": "loss"}).json()
    assert [g["lichess_id"] for g in losses["items"]] == ["Loss0001"]
    assert losses["counts"]["total"] == 3  # the counts ignore the result filter

    rated = client.get("/api/lichess/games", params={"rated": "true"}).json()
    assert [g["lichess_id"] for g in rated["items"]] == ["Draw0001", "Loss0001"]
    assert rated["counts"] == {"win": 0, "draw": 1, "loss": 1, "total": 2}

    other = client.get("/api/lichess/games", params={"generation": 7}).json()
    assert other["items"] == [] and other["counts"]["total"] == 0


def ids(client: TestClient, **params: str) -> list[str]:
    body = client.get("/api/lichess/games", params=params).json()
    return [g["lichess_id"] for g in body["items"]]


def test_the_list_finds_opponents_by_kind_name_and_speed(client: TestClient, seeded: None) -> None:
    assert ids(client, opponent="bot") == ["Draw0001", "Loss0001"]
    assert ids(client, opponent="human") == ["Win00001"]
    # Any case, any part of the name; a % is a character, not a wildcard.
    assert ids(client, q="MAIA") == ["Draw0001", "Loss0001"]
    assert ids(client, q="human%") == ["Win00001"]
    assert ids(client, q="ia%") == []
    assert ids(client, q="  ") == ["Draw0001", "Win00001", "Loss0001"]
    assert ids(client, speed="blitz") == ["Loss0001"]
    assert ids(client, speed="classical") == []
    both = client.get("/api/lichess/games", params={"q": "maia", "result": "loss"}).json()
    assert [g["lichess_id"] for g in both["items"]] == ["Loss0001"]
    assert both["counts"] == {"win": 0, "draw": 1, "loss": 1, "total": 2}


@pytest.mark.parametrize(
    ("time_control", "expected"),
    [("15+0", "ultrabullet"), ("60+0", "bullet"), ("120+1", "bullet"), ("120+2", "blitz"),
     ("180+2", "blitz"), ("300+5", "rapid"), ("480+0", "rapid"), ("1800+0", "classical"),
     ("-", "correspondence")],
)  # fmt: skip
def test_speeds_follow_the_estimated_duration(time_control: str, expected: str) -> None:
    assert lichess_history.speed_of(time_control) == expected


@pytest.mark.parametrize(
    "params",
    [{"result": "aborted"}, {"limit": 0}, {"limit": 51}, {"before_id": 0}, {"opponent": "cat"},
     {"speed": "fast"}, {"q": "x" * 65}],
)  # fmt: skip
def test_the_list_refuses_bad_parameters(
    client: TestClient, seeded: None, params: dict[str, str | int]
) -> None:
    assert client.get("/api/lichess/games", params=params).status_code == 400


def test_a_game_move_by_move(client: TestClient, seeded: None) -> None:
    body = client.get("/api/lichess/games/Loss0001").json()
    assert body["analysed"] is True
    assert body["rating_after"] == 1520
    assert [m["san"] for m in body["moves"]] == ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"]
    assert [m["ours"] for m in body["moves"]] == [False, True, False, True, False, True]
    assert [m["judgement"] for m in body["moves"]] == [None, None, None, "blunder", None, None]
    assert body["turning_point"] == 3
    assert body["sides"]["us"]["blunder"] == 1
    assert len(body["positions"]) == 7
    assert body["positions"][0]["fen"].startswith("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w")
    assert body["positions"][4] | {"fen": None} == {"fen": None, "eval_cp": -400, "chances": -63}
    assert body["commentary"] == {"it": "Persa.", "en": "Lost."}
    # The neighbours skip the aborted game and the one still being played.
    assert body["older"] is None and body["newer"] == "Win00001"
    assert client.get("/api/lichess/games/Draw0001").json()["newer"] is None


def test_a_game_without_evaluations_still_has_its_moves(client: TestClient, seeded: None) -> None:
    body = client.get("/api/lichess/games/Win00001").json()
    assert body["analysed"] is False
    assert [m["san"] for m in body["moves"]] == ["e4", "e5"]
    assert [m["judgement"] for m in body["moves"]] == [None, None]
    assert body["positions"][1].keys() == {"fen"}
    assert body["sides"] is None and body["turning_point"] is None
    assert (body["older"], body["newer"]) == ("Loss0001", "Draw0001")


@pytest.mark.parametrize(
    ("lichess_id", "status"),
    [("Abort001", 404), ("Live0001", 404), ("Nope0001", 404), ("bad-id!", 400)],
)
def test_only_finished_games_can_be_opened(
    client: TestClient, seeded: None, lichess_id: str, status: int
) -> None:
    assert client.get(f"/api/lichess/games/{lichess_id}").status_code == status
