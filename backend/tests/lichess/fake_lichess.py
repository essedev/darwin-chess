"""A fake Lichess serving the few Bot API calls the bot makes, NDJSON streams included.

Events are pushed by the test. In the one game it hosts we play white: every move we post
comes back as a gameState, followed by a scripted reply, and after `game_plies` plies the
game ends with us mated.
"""

import asyncio
import json
import random
import socket
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs

import chess
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

ME = "darwinbot"
GAME_ID = "abcd1234"
CLOCK_MS = 180_000
INC_MS = 2_000


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ndjson(items: AsyncIterator[dict[str, Any]]) -> StreamingResponse:
    async def lines() -> AsyncIterator[str]:
        async for item in items:
            yield json.dumps(item) + "\n" if item else "\n"  # {} is a keep-alive

    return StreamingResponse(lines(), media_type="application/x-ndjson")


def blitz_user(name: str, rating: int) -> dict[str, Any]:
    return {"id": name.lower(), "username": name, "title": "BOT",
            "perfs": {"blitz": {"rating": rating, "games": 100}}}  # fmt: skip


class FakeLichess:
    def __init__(self, *, bots: list[dict[str, Any]] | None = None, game_plies: int = 12) -> None:
        self.bots = bots if bots is not None else [blitz_user("DarwinBot", 1500)]
        self.game_plies = game_plies
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.states: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.board = chess.Board()
        self.rng = random.Random(7)
        self.accepted: list[str] = []
        self.declined: list[tuple[str, str]] = []
        self.challenged: list[tuple[str, dict[str, str]]] = []
        self.refusing: set[str] = set()  # bots whose challenge Lichess rejects at once
        # The next challenges answered 429, each with its wait in seconds (None: not said).
        self.rate_limits: list[float | None] = []
        self.challenged_at: list[float] = []
        self.refused_moves: list[str] = []

    def start_game(self) -> None:
        self.events.put_nowait({"type": "gameStart", "game": {
            "gameId": GAME_ID, "color": "white", "rated": True, "speed": "blitz",
            "opponent": {"id": "oppbot", "username": "OppBot", "rating": 1600},
        }})  # fmt: skip

    def _state(self, status: str = "started", winner: str | None = None) -> dict[str, Any]:
        state: dict[str, Any] = {
            "type": "gameState",
            "moves": " ".join(move.uci() for move in self.board.move_stack),
            "wtime": CLOCK_MS, "btime": CLOCK_MS, "winc": INC_MS, "binc": INC_MS,
            "status": status,
        }  # fmt: skip
        if winner:
            state["winner"] = winner
        return state

    def _play(self, uci: str) -> bool:
        move = chess.Move.from_uci(uci)
        if self.board.turn != chess.WHITE or move not in self.board.legal_moves:
            return False
        self.board.push(move)
        self.states.put_nowait(self._state())
        if not self.board.is_game_over():
            replies = sorted(self.board.legal_moves, key=lambda m: m.uci())
            self.board.push(self.rng.choice(replies))
        over = len(self.board.move_stack) >= self.game_plies or self.board.is_game_over()
        self.states.put_nowait(self._state("mate", "black") if over else self._state())
        return True

    def app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/api/account")
        async def account() -> dict[str, Any]:
            return blitz_user("DarwinBot", 1500)

        @app.get("/api/stream/event")
        async def events() -> StreamingResponse:
            async def items() -> AsyncIterator[dict[str, Any]]:
                while True:
                    try:
                        yield await asyncio.wait_for(self.events.get(), 1.0)
                    except TimeoutError:
                        yield {}

            return ndjson(items())

        @app.get("/api/bot/online")
        async def online() -> StreamingResponse:
            async def items() -> AsyncIterator[dict[str, Any]]:
                for bot in self.bots:
                    yield bot

            return ndjson(items())

        @app.post("/api/challenge/{challenge_id}/accept")
        async def accept(challenge_id: str) -> dict[str, Any]:
            self.accepted.append(challenge_id)
            return {"ok": True}

        @app.post("/api/challenge/{challenge_id}/decline")
        async def decline(challenge_id: str, request: Request) -> dict[str, Any]:
            form = parse_qs((await request.body()).decode())
            self.declined.append((challenge_id, form.get("reason", [""])[0]))
            return {"ok": True}

        @app.post("/api/challenge/{username}")
        async def challenge(username: str, request: Request) -> Any:
            form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
            self.challenged.append((username, form))
            self.challenged_at.append(time.monotonic())
            if self.rate_limits:
                seconds = self.rate_limits.pop(0)
                body: dict[str, Any] = {"error": "Too many requests. Try again later."}
                if seconds is not None:
                    body["ratelimit"] = {"seconds": seconds}
                return JSONResponse(body, 429)
            if username in self.refusing:
                return JSONResponse({"error": f"{username} played 100 games today"}, 400)
            return {"id": "out1", "status": "created"}

        @app.get("/api/bot/game/stream/{game_id}")
        async def game(game_id: str) -> StreamingResponse:
            async def items() -> AsyncIterator[dict[str, Any]]:
                yield {
                    "type": "gameFull", "id": game_id, "rated": True, "speed": "blitz",
                    "white": {"id": ME, "name": "DarwinBot", "rating": 1500, "title": "BOT"},
                    "black": {"id": "oppbot", "name": "OppBot", "rating": 1600, "title": "BOT"},
                    "initialFen": "startpos",
                    "clock": {"initial": CLOCK_MS, "increment": INC_MS},
                    "state": self._state(),
                }  # fmt: skip
                while True:
                    state = await self.states.get()
                    yield state
                    if state["status"] != "started":
                        return

            return ndjson(items())

        @app.post("/api/bot/game/{game_id}/move/{uci}", response_model=None)
        async def move(game_id: str, uci: str) -> dict[str, Any] | JSONResponse:
            if not self._play(uci):
                self.refused_moves.append(uci)
                return JSONResponse({"error": "Not your turn, or game already over"}, 400)
            return {"ok": True}

        return app


async def serve(fake: FakeLichess) -> tuple[uvicorn.Server, asyncio.Task[None], str]:
    port = free_port()
    config = uvicorn.Config(fake.app(), host="127.0.0.1", port=port, log_level="warning",
                            timeout_graceful_shutdown=2)  # fmt: skip
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110  (uvicorn exposes a flag, not an event)
        await asyncio.sleep(0.05)
    return server, task, f"http://127.0.0.1:{port}"
