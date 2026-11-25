"""The few Lichess Bot API calls the bot needs. Streams are NDJSON; empty lines are
keep-alives. The token never leaves this process."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

log = logging.getLogger(__name__)


class LichessError(Exception):
    pass


class RateLimited(LichessError):
    """HTTP 429. `wait_s` is how long Lichess asked to wait, when the answer says it;
    `detail` is the answer itself, for the log."""

    def __init__(self, path: str, wait_s: float | None = None, detail: str = "") -> None:
        super().__init__(f"{path}: 429 {detail}".rstrip())
        self.wait_s = wait_s
        self.detail = detail


async def rate_limited(path: str, response: httpx.Response) -> RateLimited:
    """Reads the wait from the body (`{"ratelimit": {"seconds": n}}`, as Lichess answers a
    challenge) or from Retry-After."""
    await response.aread()
    detail = response.text[:300]
    wait: float | None = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("ratelimit"), dict):
        seconds = body["ratelimit"].get("seconds")
        if isinstance(seconds, int | float) and seconds > 0:
            wait = float(seconds)
    header = response.headers.get("Retry-After", "")
    if wait is None and header.isdigit() and int(header) > 0:
        wait = float(header)
    return RateLimited(path, wait, detail)


class LichessClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(30.0, read=None),  # streams stay open for hours
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _post(self, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.post(path, data=data)
        if response.status_code == 429:
            raise await rate_limited(path, response)
        if response.status_code >= 400:
            raise LichessError(f"POST {path}: {response.status_code} {response.text[:200]}")
        return response.json() if response.content else {}

    async def _stream(self, path: str) -> AsyncIterator[dict[str, Any]]:
        async with self._http.stream("GET", path) as response:
            if response.status_code == 429:
                raise await rate_limited(path, response)
            if response.status_code >= 400:
                raise LichessError(f"GET {path}: {response.status_code}")
            async for line in response.aiter_lines():
                if line.strip():
                    yield json.loads(line)

    async def account(self) -> dict[str, Any]:
        response = await self._http.get("/api/account")
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    def events(self) -> AsyncIterator[dict[str, Any]]:
        return self._stream("/api/stream/event")

    def game(self, game_id: str) -> AsyncIterator[dict[str, Any]]:
        return self._stream(f"/api/bot/game/stream/{game_id}")

    async def move(self, game_id: str, uci: str) -> None:
        await self._post(f"/api/bot/game/{game_id}/move/{uci}")

    async def accept(self, challenge_id: str) -> None:
        await self._post(f"/api/challenge/{challenge_id}/accept")

    async def decline(self, challenge_id: str, reason: str) -> None:
        await self._post(f"/api/challenge/{challenge_id}/decline", {"reason": reason})

    async def challenge(self, username: str, clock_s: int, increment_s: int) -> None:
        await self._post(f"/api/challenge/{username}", {
            "rated": "true", "clock.limit": str(clock_s), "clock.increment": str(increment_s),
            "color": "random", "variant": "standard",
        })  # fmt: skip

    async def online_bots(self, count: int = 100) -> list[dict[str, Any]]:
        bots = []
        async for bot in self._stream(f"/api/bot/online?nb={count}"):
            bots.append(bot)
        return bots
