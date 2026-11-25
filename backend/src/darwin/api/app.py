"""Read-only API for the dashboard: overview, live game, Lichess, history, code and memory, and a
server-sent event stream.

The API never writes: it reads the ledger (SQLite in WAL, while core writes), the fastchess
event streams under the data dir, the file the Lichess bot keeps for its current game, the
trusted git mirror and the agent's memory files (`explore.py`).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from darwin.api.code import BadRequest, GitError, Mirror, NotFound
from darwin.api.explore import router as explore_router
from darwin.api.hub import Full, Hub
from darwin.api.lichess_live import read_lichess_live
from darwin.api.live import read_live_game
from darwin.config import get_settings
from darwin.ledger import queries
from darwin.ledger.store import Ledger
from darwin.orchestrator.budget import allowance, day_start

STREAM_TICK_S = 1.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.ledger = Ledger(settings.ledger_url)
    app.state.mirror = Mirror(settings.mirror_dir)
    data_dir = settings.data_dir
    app.state.hub = Hub(
        app.state.ledger,
        {
            "game": lambda: read_live_game(data_dir / "matches"),
            "lichess": lambda: read_lichess_live(data_dir),
        },
    )
    await app.state.hub.start()
    yield
    await app.state.hub.stop()
    await app.state.ledger.close()


# Public, read-only: no generated docs or schema to browse.
app = FastAPI(
    title="darwin-chess", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)
app.include_router(explore_router)


def _error(status: int) -> Any:
    async def handler(_: Request, exc: Exception) -> JSONResponse:
        detail = "bad parameters" if isinstance(exc, RequestValidationError) else str(exc)
        return JSONResponse({"detail": detail}, status_code=status)

    return handler


# Bad parameters are 400, not FastAPI's 422; git failures are not the caller's fault.
app.add_exception_handler(RequestValidationError, _error(400))
app.add_exception_handler(BadRequest, _error(400))
app.add_exception_handler(NotFound, _error(404))
app.add_exception_handler(GitError, _error(503))


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
        "jobs": await queries.jobs_view(ledger),
    }


@app.get("/api/live")
async def live() -> dict[str, Any] | None:
    return await asyncio.to_thread(read_live_game, get_settings().data_dir / "matches")


@app.get("/api/lichess")
async def lichess(request: Request) -> dict[str, Any]:
    ledger: Ledger = request.app.state.ledger
    settings = get_settings()
    live = await asyncio.to_thread(read_lichess_live, settings.data_dir)
    summary = await queries.lichess_summary(ledger, settings.lichess_url, settings.lichess_account)
    return {"live": live, **summary}


def _serve_dashboard() -> None:
    dist = get_settings().frontend_dist
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    hub: Hub = request.app.state.hub
    try:
        queue = hub.subscribe()
    except Full as exc:
        raise HTTPException(503, "too many live viewers, retry later") from exc

    async def events() -> AsyncIterator[str]:
        try:
            while not await request.is_disconnected():
                try:
                    yield await asyncio.wait_for(queue.get(), STREAM_TICK_S * 15)
                except TimeoutError:
                    yield ": keep-alive\n\n"  # proxies close idle streams
        finally:
            hub.unsubscribe(queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_serve_dashboard()  # after the API routes, so /api/* wins
