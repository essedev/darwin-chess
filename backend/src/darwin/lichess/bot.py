"""The Lichess bot: the champion of the time plays on Lichess, one game at a time.

This is the lobby: it keeps the event stream open, accepts fitting challenges, challenges
bots of similar rating when idle, and hands each game to `game.Game`. Nothing here may
bring core down: every failure is logged and the bot reconnects with backoff.
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.lichess import rules
from darwin.lichess.client import LichessClient, LichessError, RateLimited
from darwin.lichess.game import Game
from darwin.referee.models import EngineSpec

log = logging.getLogger(__name__)

# The champion's generation and engine, or None while there is no champion (gen-0).
EngineFor = Callable[[], Awaitable[tuple[int, EngineSpec] | None]]

MAX_BACKOFF_S = 60.0
RATE_LIMIT_S = 61.0  # Lichess asks for at least a minute after a 429
PENDING_TTL_S = 60.0


CHALLENGE_ATTEMPTS = 5
MIN_CHALLENGE_GAP_S = 5.0  # between two matchmaking rounds, even when a decline wakes it


class LichessBot:
    def __init__(
        self,
        settings: Settings,
        ledger: Ledger,
        client: LichessClient,
        engine_for: EngineFor,
        *,
        rng: random.Random | None = None,
        max_games: int | None = None,
    ) -> None:
        self.settings = settings
        self.ledger = ledger
        self.client = client
        self.engine_for = engine_for
        self.rng = rng or random.Random()
        self.speed = rules.speed_of(settings.lichess_clock_s, settings.lichess_increment_s)
        self.me = ""  # our account id, lowercase
        self.rating = rules.DEFAULT_RATING
        self.game: asyncio.Task[None] | None = None
        self.game_id: str | None = None
        # A challenge we sent or accepted whose game has not started yet.
        self.pending_id: str | None = None
        self.pending_since: float | None = None
        # Trial runs stop after a number of games; the service plays forever.
        self.max_games = max_games
        self.games_played = 0
        self.finished = asyncio.Event()
        # A decline wakes matchmaking at once; who declined is not asked again this run.
        self.retry = asyncio.Event()
        self.declined_by: set[str] = set()

    def enough(self) -> bool:
        return self.max_games is not None and self.games_played >= self.max_games

    async def run(self) -> None:
        matchmaking = asyncio.create_task(self._matchmaking())
        listening = asyncio.create_task(self._listen())
        stopping = asyncio.create_task(self.finished.wait())
        try:
            await asyncio.wait({listening, stopping}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            tasks = [t for t in (matchmaking, listening, stopping, self.game) if t is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def busy(self) -> bool:
        if self.pending_since is not None and time.monotonic() - self.pending_since > PENDING_TTL_S:
            log.info("lichess: challenge %s got no game in time, forgetting it", self.pending_id)
            self._clear_pending()
        playing = self.game is not None and not self.game.done()
        return playing or self.pending_since is not None

    def _clear_pending(self) -> None:
        self.pending_id = self.pending_since = None

    async def _identify(self) -> None:
        account = await self.client.account()
        self.me = str(account.get("id") or account.get("username") or "").lower()
        self.rating = rules.matchmaking_rating(
            account, self.speed, self.settings.lichess_start_rating
        )

    # Incoming events

    async def _listen(self) -> None:
        backoff = 1.0
        while True:
            try:
                await self._identify()
                async for event in self.client.events():
                    backoff = 1.0
                    await self._on_event(event)
                log.info("lichess: event stream closed, reconnecting")
            except RateLimited:
                log.warning("lichess: rate limited, waiting %.0f s", RATE_LIMIT_S)
                await asyncio.sleep(RATE_LIMIT_S)
                continue
            except Exception:
                log.exception("lichess: event stream failed")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    async def _on_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        try:
            if kind == "challenge":
                await self._on_challenge(event["challenge"])
            elif kind == "gameStart":
                self._on_game_start(event["game"])
            elif kind in {"challengeDeclined", "challengeCanceled"}:
                challenge = event.get("challenge") or {}
                challenger = str((challenge.get("challenger") or {}).get("id", "")).lower()
                if challenge.get("id") == self.pending_id or challenger == self.me:
                    self._clear_pending()
                    opponent = str((challenge.get("destUser") or {}).get("name", ""))
                    reason = challenge.get("declineReason") or kind
                    log.info("lichess: %s did not accept (%s), trying another", opponent, reason)
                    if opponent:
                        self.declined_by.add(opponent.lower())
                    self.retry.set()
        except RateLimited:
            raise
        except Exception:  # one bad event must not drop the stream
            log.exception("lichess: cannot handle a %s event", kind)

    async def _on_challenge(self, challenge: dict[str, Any]) -> None:
        challenge_id = str(challenge["id"])
        challenger = challenge.get("challenger") or {}
        if str(challenger.get("id", "")).lower() == self.me:  # our own, echoed back
            self.pending_id = challenge_id
            return
        reason = rules.decline_reason(challenge, busy=self.busy())
        if reason is None and await self.engine_for() is None:
            reason = "later"
        if reason is not None:
            name = challenger.get("name")
            log.info("lichess: declining %s from %s (%s)", challenge_id, name, reason)
            await self.client.decline(challenge_id, reason)
            return
        log.info("lichess: accepting %s from %s", challenge_id, challenger.get("name"))
        self.pending_id, self.pending_since = challenge_id, time.monotonic()
        await self.client.accept(challenge_id)

    def _on_game_start(self, game: dict[str, Any]) -> None:
        game_id = str(game.get("gameId") or game["id"])
        self._clear_pending()
        if self.game is not None and not self.game.done():
            if self.game_id != game_id:
                log.warning("lichess: %s started during %s, not playing it", game_id, self.game_id)
            return
        color = game.get("color")
        self.game_id = game_id
        self.game = asyncio.create_task(
            self._play(game_id, color if color in {"white", "black"} else None)
        )

    # Matchmaking

    async def _matchmaking(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self.retry.wait(), self.settings.lichess_challenge_every_s)
                await asyncio.sleep(MIN_CHALLENGE_GAP_S)
            except TimeoutError:
                pass
            self.retry.clear()
            try:
                await self._challenge_someone()
            except RateLimited:
                log.warning("lichess: rate limited while matchmaking")
                await asyncio.sleep(RATE_LIMIT_S)
            except Exception:
                log.exception("lichess: matchmaking failed")

    async def _challenge_someone(self) -> None:
        if self.enough():
            return
        if self.busy() or await self.engine_for() is None:
            return
        await self._identify()
        bots = [
            b
            for b in await self.client.online_bots()
            if str(b.get("username") or b.get("id") or "").lower() not in self.declined_by
        ]
        # Lichess refuses some challenges outright (an opponent's daily cap, its own rules):
        # try another bot at once instead of losing a matchmaking round.
        for _attempt in range(CHALLENGE_ATTEMPTS):
            name = rules.pick_opponent(
                bots, me=self.me, my_rating=self.rating, speed=self.speed, rng=self.rng
            )
            if name is None:
                log.info("lichess: no online bot near %d in %s", self.rating, self.speed)
                return
            self.pending_id, self.pending_since = None, time.monotonic()
            try:
                await self.client.challenge(
                    name, self.settings.lichess_clock_s, self.settings.lichess_increment_s
                )
            except RateLimited:
                self._clear_pending()
                raise
            except LichessError as refused:
                self._clear_pending()
                log.info("lichess: %s refused at once (%s), trying another", name, refused)
                bots = [b for b in bots if str(b.get("username") or b.get("id") or "") != name]
                continue
            log.info("lichess: challenged %s", name)
            return

    # One game

    async def _play(self, game_id: str, color: str | None) -> None:
        try:
            choice = await self.engine_for()
        except Exception:
            log.exception("lichess: no engine for game %s", game_id)
            return
        if choice is None:
            log.warning("lichess: game %s started without a champion, not playing", game_id)
            return
        game = Game(
            self.settings, self.ledger, self.client, game_id=game_id, color=color, me=self.me
        )
        try:
            await game.play(*choice)
        finally:
            self.games_played += 1
            if self.enough():
                self.finished.set()
