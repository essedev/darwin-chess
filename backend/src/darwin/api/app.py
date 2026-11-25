"""Read-only API for the dashboard: overview, live game, and a server-sent event stream.

The API never writes: it reads the ledger (SQLite in WAL, while core writes) and the
fastchess event streams under the data dir.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from darwin.api.live import read_live_game
from darwin.config import get_settings
from darwin.ledger import queries
from darwin.ledger.store import Ledger
from darwin.orchestrator.budget import allowance, day_start

STREAM_TICK_S = 1.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.ledger = Ledger(get_settings().ledger_url)
    yield
    await app.state.ledger.close()


app = FastAPI(title="darwin-chess", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
async def overview(request: Request) -> dict[str, Any]:
    ledger: Ledger = request.app.state.ledger
    settings = get_settings()
    now = datetime.now(UTC)
    try:
        state = await ledger.state()
    except LookupError:
        return {"ready": False}
    latest = await queries.latest_experiments(ledger, 1)
    current = [await queries.experiment_view(ledger, row) for row in latest]
    previous = await queries.latest_experiments(ledger, 2)
    spent = await queries.spend(ledger, day_start(now))
    running = bool(latest) and latest[0].status in {"running", "judging"}
    quota = allowance(now, settings.daily_budget_usd)
    paused = spent["usd"] + settings.session_max_usd > quota
    return {
        "ready": True,
        "phase": state.phase.value,
        "champion": {"id": state.champion.id, "commit": state.champion.commit_sha},
        "generations": await queries.generations_with_story(ledger),
        "experiments": await queries.experiment_counts(ledger),
        "current": current[0] if current else None,
        "previous": await queries.experiment_view(ledger, previous[1])
        if len(previous) > 1
        else None,
        "agent": "paused" if paused and not running else ("working" if running else "idle"),
        "spend": {**spent, "budget": settings.daily_budget_usd, "quota_now": quota},
        "events": await queries.recent_events(ledger, 30),
    }


@app.get("/api/live")
async def live() -> dict[str, Any] | None:
    return await asyncio.to_thread(read_live_game, get_settings().data_dir / "matches")


def _serve_dashboard() -> None:
    dist = get_settings().frontend_dist
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    ledger: Ledger = request.app.state.ledger
    matches = get_settings().data_dir / "matches"

    async def events() -> AsyncIterator[str]:
        last_id = await queries.last_event_id(ledger)
        last_game: str | None = None
        while not await request.is_disconnected():
            for event in await queries.events_after(ledger, last_id):
                last_id = event["id"]
                yield f"event: agent\ndata: {json.dumps(event)}\n\n"
            game = await asyncio.to_thread(read_live_game, matches)
            encoded = json.dumps(game)
            if encoded != last_game:
                last_game = encoded
                yield f"event: game\ndata: {encoded}\n\n"
            await asyncio.sleep(STREAM_TICK_S)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


_serve_dashboard()  # after the API routes, so /api/* wins
