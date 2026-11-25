"""One Lichess game, start to end: the champion's engine moves on our turns, the game goes
to the ledger, a loss is analysed by Stockfish, and `<data>/lichess/current.json` mirrors
every state for the dashboard (the last game stays there once it is over)."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from darwin.config import Settings
from darwin.ledger import lichess as records
from darwin.ledger.store import Ledger
from darwin.lichess import rules
from darwin.lichess.client import LichessClient, LichessError, RateLimited
from darwin.referee import analysis, uci
from darwin.referee.models import EngineSpec

log = logging.getLogger(__name__)

MAX_BACKOFF_S = 60.0
RATE_LIMIT_S = 61.0  # Lichess asks for at least a minute after a 429
THINK_MARGIN_S = 5.0
MOVE_OVERHEAD_MS = 300
MIN_PLIES_FOR_ANALYSIS = 10
RATING_SETTLE_S = 2.0  # Lichess updates the rating right after the game, give it a moment
GAME_STREAM_RETRIES = 8
MOVE_RETRIES = 3


@dataclass
class LiveGame:
    game_id: str
    generation: int
    color: str
    opponent: dict[str, Any]
    time_control: str
    initial_fen: str
    speed: str
    moves: list[str] = field(default_factory=list)
    wtime: int = 0
    btime: int = 0
    winc: int = 0
    binc: int = 0
    status: str = "started"
    result: str | None = None

    def update(self, state: dict[str, Any]) -> None:
        self.moves = str(state.get("moves") or "").split()
        self.wtime = int(state.get("wtime", self.wtime))
        self.btime = int(state.get("btime", self.btime))
        self.winc = int(state.get("winc", self.winc))
        self.binc = int(state.get("binc", self.binc))
        self.status = str(state.get("status", self.status))
        self.result = rules.result_for(self.status, state.get("winner"), self.color)

    def snapshot(self) -> dict[str, Any]:
        """The contract of current.json, read by the API."""
        return {
            "game_id": self.game_id,
            "url": f"https://lichess.org/{self.game_id}",
            "generation": self.generation,
            "color": self.color,
            "opponent": self.opponent,
            "time_control": self.time_control,
            "initial_fen": self.initial_fen,
            "moves": self.moves,
            "wtime": self.wtime,
            "btime": self.btime,
            "status": self.status,
            "result": self.result,
            "updated_at": datetime.now(UTC).isoformat(),
        }


class Game:
    def __init__(
        self,
        settings: Settings,
        ledger: Ledger,
        client: LichessClient,
        *,
        game_id: str,
        color: str | None,
        me: str,
    ) -> None:
        self.settings = settings
        self.ledger = ledger
        self.client = client
        self.game_id = game_id
        self.color = color  # from gameStart; None: worked out from the players
        self.me = me
        self.live: LiveGame | None = None
        self.live_path = settings.data_dir / "lichess" / "current.json"

    async def play(self, generation: int, spec: EngineSpec) -> None:
        """Never raises (except cancellation): failures are logged, the end still recorded."""
        try:
            try:
                async with uci.session(self.settings, spec) as engine:
                    engine.send("ucinewgame")
                    await self._follow(generation, engine)
            except uci.EngineFault:  # only the handshake raises it: `_think` catches its own
                if self.live is not None:
                    raise
                log.exception("lichess: the engine of gen-%d did not start", generation)
                await self._follow(generation, None)  # record the game anyway
        except Exception:
            log.exception("lichess: game %s failed", self.game_id)
        live = self.live
        if live is not None and live.result is not None:
            try:
                await self._record_end(live)
            except Exception:
                log.exception("lichess: cannot record the end of %s", self.game_id)

    async def _follow(self, generation: int, engine: uci.UciSession | None) -> None:
        """Follow the game stream to the end, moving on our turns while the engine works."""
        game_id = self.game_id
        answered = -1  # plies at our last move: never answer the same position twice
        failures = 0
        while True:
            try:
                async for event in self.client.game(self.game_id):
                    failures = 0
                    if event.get("type") == "gameFull":
                        await self._on_full(generation, event)
                        state = event["state"]
                    elif event.get("type") == "gameState":
                        state = event
                    else:
                        continue
                    live = self.live
                    if live is None:
                        continue
                    live.update(state)
                    self._write_live(live)
                    if live.status not in rules.UNFINISHED:
                        return
                    if (
                        engine is None
                        or len(live.moves) == answered
                        or not rules.our_turn(live.initial_fen, len(live.moves), live.color)
                    ):
                        continue
                    move = await self._think(engine, live)
                    if move is None:
                        engine = None  # stop moving: the clock will flag us
                        continue
                    if await self._send_move(move):
                        answered = len(live.moves)
                log.warning("lichess: stream of %s ended before the game", game_id)
            except RateLimited:
                log.warning("lichess: rate limited on %s", game_id)
                await asyncio.sleep(RATE_LIMIT_S)
            except (LichessError, httpx.HTTPError, ValueError):
                log.exception("lichess: stream of %s failed", game_id)
            failures += 1
            if failures > GAME_STREAM_RETRIES:
                log.error("lichess: giving up on the stream of %s", game_id)
                return
            await asyncio.sleep(min(2.0**failures, MAX_BACKOFF_S))

    async def _on_full(self, generation: int, full: dict[str, Any]) -> None:
        if self.live is not None:
            return  # the stream reconnected
        game_id, color = self.game_id, self.color
        white, black = full.get("white") or {}, full.get("black") or {}
        if color is None:
            color = "white" if str(white.get("id", "")).lower() == self.me else "black"
        side = black if color == "white" else white
        name = side.get("name") or (f"AI level {side['aiLevel']}" if "aiLevel" in side else "?")
        clock = full.get("clock") or {}
        limit_s, increment_s = clock.get("initial", 0) // 1000, clock.get("increment", 0) // 1000
        rating = side.get("rating")
        rating = int(rating) if isinstance(rating, int | float) else None
        title = str(side["title"]) if side.get("title") else None
        opponent = {"name": str(name), "rating": rating, "title": title}
        self.live = LiveGame(
            game_id=game_id,
            generation=generation,
            color=color,
            opponent=opponent,
            time_control=f"{limit_s}+{increment_s}" if clock else "-",
            initial_fen=str(full.get("initialFen") or rules.STARTPOS),
            speed=str(full.get("speed") or rules.speed_of(limit_s, increment_s)),
        )
        await records.start_game(
            self.ledger,
            lichess_id=game_id,
            generation_id=generation,
            color=color,
            opponent=str(name)[:64],
            opponent_rating=rating,
            opponent_title=title,
            rated=bool(full.get("rated")),
            time_control=self.live.time_control,
        )
        log.info("lichess: game %s, gen-%d as %s against %s", game_id, generation, color, name)

    async def _think(self, engine: uci.UciSession, live: LiveGame) -> str | None:
        board = rules.board_for(live.initial_fen, live.moves)
        engine.send(rules.position_command(live.initial_fen, live.moves))
        go = rules.go_command(
            wtime=live.wtime,
            btime=live.btime,
            winc=live.winc,
            binc=live.binc,
            color=live.color,
            overhead_ms=MOVE_OVERHEAD_MS,
        )
        engine.send(go)
        ours_ms = live.wtime if live.color == "white" else live.btime
        try:
            lines = await engine.read_until("bestmove", ours_ms / 1000 + THINK_MARGIN_S)
        except uci.EngineFault:
            log.exception("lichess: engine fault in %s", live.game_id)
            return None
        parts = lines[-1].split()
        move = parts[1] if len(parts) > 1 else ""
        if not rules.is_legal(board, move):
            log.error("lichess: illegal move %r in %s", move, live.game_id)
            return None
        return move

    async def _send_move(self, move: str) -> bool:
        game_id = self.game_id
        for attempt in range(1, MOVE_RETRIES + 1):
            try:
                await self.client.move(game_id, move)
                return True
            except LichessError:  # refused: game over, not our turn, rate limited
                log.exception("lichess: move %s refused in %s", move, game_id)
                return False
            except httpx.HTTPError:
                log.warning("lichess: move %s not sent (attempt %d)", move, attempt)
                await asyncio.sleep(0.5)
        return False

    async def _record_end(self, live: LiveGame) -> None:
        assert live.result is not None
        log.info("lichess: game %s over, %s (%s)", live.game_id, live.result, live.status)
        rating_after = await self._rating_now(live.speed)
        row_id = await records.finish_game(
            self.ledger,
            live.game_id,
            status=live.status,
            result=live.result,
            moves=" ".join(live.moves),
            rating_after=rating_after,
        )
        if (
            live.result != "loss"
            or len(live.moves) < MIN_PLIES_FOR_ANALYSIS
            or live.initial_fen != rules.STARTPOS  # the analysis replays from the start
        ):
            return
        try:
            worst = await analysis.worst_move(self.settings, live.moves, live.color)
            await records.set_analysis(self.ledger, row_id, worst)
        except Exception:
            log.exception("lichess: analysis of %s failed", live.game_id)

    async def _rating_now(self, speed: str) -> int | None:
        await asyncio.sleep(RATING_SETTLE_S)
        try:
            account = await self.client.account()
        except (httpx.HTTPError, ValueError):
            log.warning("lichess: cannot read the rating after the game", exc_info=True)
            return None
        return rules.rating_of(account, speed)

    def _write_live(self, live: LiveGame) -> None:
        try:
            self.live_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.live_path.with_name(self.live_path.name + ".tmp")
            tmp.write_text(json.dumps(live.snapshot()))
            os.replace(tmp, self.live_path)
        except OSError:
            log.exception("lichess: cannot write %s", self.live_path)
