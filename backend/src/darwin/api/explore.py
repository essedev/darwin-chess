"""Read-only routes to explore the lab's history: generations, experiments, matches, code,
memory.

Errors from the mirror (`code.BadRequest`, `code.NotFound`, `code.GitError`) become HTTP
responses through the handlers registered in `app.py`.
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request

from darwin.api.code import BadRequest, Mirror, NotFound
from darwin.api.mind import read_changelog, read_mind
from darwin.config import get_settings
from darwin.ledger import history
from darwin.ledger.store import Ledger
from darwin.orchestrator.prompts import SYSTEM

router = APIRouter(prefix="/api")


def _ledger(request: Request) -> Ledger:
    ledger: Ledger = request.app.state.ledger
    return ledger


def _mirror(request: Request) -> Mirror:
    mirror: Mirror = request.app.state.mirror
    return mirror


@router.get("/generations/detail")
async def generations_detail(request: Request) -> list[dict[str, Any]]:
    return await history.generations_detail(_ledger(request))


@router.get("/experiments")
async def experiments(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    status: Annotated[str | None, Query(max_length=200, pattern=r"^[a-z_]+(,[a-z_]+)*$")] = None,
) -> dict[str, Any]:
    """`status` is a comma-separated list: "rejected,stale,abandoned"."""
    statuses = status.split(",") if status else []
    return await history.experiments_page(_ledger(request), limit, before_id, statuses)


@router.get("/matches")
async def matches(
    request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> list[dict[str, Any]]:
    return await history.recent_matches(_ledger(request), limit)


async def _ref_or_champion(request: Request, ref: str | None) -> str:
    if ref is not None:
        return ref
    try:
        state = await _ledger(request).state()
    except LookupError as exc:
        raise HTTPException(404, "no champion yet") from exc
    return f"gen-{state.champion.id}"


async def _generation(request: Request, ref: str, commit: str) -> int | None:
    found = await history.generation_of(_ledger(request), commit)
    if found is None and ref.startswith("gen-"):
        return int(ref.removeprefix("gen-"))
    return found


@router.get("/code/tree")
async def code_tree(request: Request, ref: str | None = None) -> dict[str, Any]:
    ref = await _ref_or_champion(request, ref)
    mirror = _mirror(request)
    commit = await mirror.resolve(ref)
    return {
        "ref": ref,
        "commit": commit,
        "generation": await _generation(request, ref, commit),
        "files": await mirror.tree(commit),
    }


@router.get("/code/file")
async def code_file(request: Request, path: str, ref: str | None = None) -> dict[str, Any]:
    ref = await _ref_or_champion(request, ref)
    mirror = _mirror(request)
    commit = await mirror.resolve(ref)
    return {"ref": ref, "commit": commit, **await mirror.file(commit, path)}


@router.get("/code/diff")
async def code_diff(
    request: Request,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
    gen: Annotated[int | None, Query(ge=1)] = None,
    exp: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, Any]:
    by_refs = from_ is not None or to is not None
    if by_refs + (gen is not None) + (exp is not None) != 1:
        raise BadRequest("give either from and to, or gen, or exp")
    mirror = _mirror(request)
    if gen is not None:
        base = await mirror.resolve(f"gen-{gen - 1}")
        head = await mirror.resolve(f"gen-{gen}")
    elif exp is not None:
        commits = await history.experiment_commits(_ledger(request), exp)
        if commits is None or commits[1] is None:
            raise NotFound(f"experiment {exp} has no candidate")
        try:
            base, head = await mirror.resolve(commits[0]), await mirror.resolve(commits[1])
        except BadRequest as exc:  # a ledger value, not the caller's
            raise NotFound(f"experiment {exp} has no commits in the mirror") from exc
    else:
        if from_ is None or to is None:
            raise BadRequest("from and to go together")
        base, head = await mirror.resolve(from_), await mirror.resolve(to)
    return {"from": base, "to": head, "files": await mirror.diff(base, head)}


@router.get("/mind")
async def mind() -> dict[str, Any]:
    return await asyncio.to_thread(read_mind, get_settings().data_dir, SYSTEM)


@router.get("/lab")
async def lab(request: Request) -> dict[str, Any]:
    summary = await history.lab_summary(_ledger(request))
    settings = get_settings()
    changelog = await asyncio.to_thread(read_changelog, settings.changelog_path)
    changelog_en = await asyncio.to_thread(read_changelog, settings.changelog_en_path)
    return {**summary, "changelog": changelog, "changelog_en": changelog_en}
