"""The darwin tools behind the pi extension: a local HTTP API, one bearer token per session.

The extension only forwards; everything that needs trust (the referee, the ledger, the
mirror, jobs) happens here, in the orchestrator's process.
"""

import asyncio
import logging
import random
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import chess
from fastapi import FastAPI, Header, HTTPException, Request

from darwin.config import Settings
from darwin.ledger import lichess
from darwin.ledger import models as m
from darwin.ledger.store import Ledger
from darwin.orchestrator import sandbox
from darwin.orchestrator.jobs import JobError, Jobs
from darwin.orchestrator.sandbox import Sandbox
from darwin.referee import engines, perft, uci
from darwin.referee.models import Binary

log = logging.getLogger(__name__)

# Told of texts written for the record: (kind, experiment id), "hypothesis" or "lesson".
Notify = Callable[[str, int], None]


class ToolError(Exception):
    """Shown to the agent as the tool's error message."""


@dataclass
class SessionTools:
    settings: Settings
    ledger: Ledger
    jobs: Jobs
    sandbox: Sandbox
    experiment_id: int
    base_commit: str
    previous_experiment_id: int | None
    submitted: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    notify: Notify | None = None  # set by the router

    def _notify(self, kind: str, experiment_id: int) -> None:
        if self.notify is None:
            return
        try:
            self.notify(kind, experiment_id)
        except Exception:  # a listener must never break the agent's tool
            log.exception("tools: notifying %s of %d failed", kind, experiment_id)

    async def call(self, tool: str, params: dict[str, Any]) -> str:
        if self.submitted is not None:
            raise ToolError("You already submitted: this session is over. Stop now.")
        handler = {
            "perft_check": self.perft_check,
            "submit": self.submit,
            "experiments": self.experiments,
            "run_job": self.run_job,
            "lichess_losses": self.lichess_losses,
        }.get(tool)
        if handler is None:
            raise ToolError(f"unknown tool {tool}")
        async with self.lock:  # one darwin tool at a time per session
            return await handler(params)

    async def perft_check(self, params: dict[str, Any]) -> str:
        built = self.settings.genome_dir / "target" / "release" / "genome"
        # The path is the agent's: never follow a link out of the genome.
        if not built.resolve().is_relative_to(self.settings.genome_dir):
            raise ToolError("target/release/genome must be a regular file inside /genome.")
        if not built.is_file():
            raise ToolError("No target/release/genome: run `cargo build --release` first.")
        scratch = self.settings.data_dir / "scratch" / f"exp-{self.experiment_id}"
        scratch.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(built, scratch / "genome")  # a frozen copy, mounted read-only
        (scratch / "genome").chmod(0o755)
        spec = engines.candidate(self.settings, Binary("working-tree", scratch), name="candidate")
        fen = params.get("fen")
        if fen:
            depth = min(int(params.get("depth") or 3), 4)
            try:
                fens = [chess.Board(fen).fen()]
            except ValueError as exc:
                raise ToolError(f"invalid FEN: {exc}") from exc
        else:
            depth = min(int(params.get("depth") or 3), 3)
            fens = perft.random_positions(random.Random(), 8)
        try:
            problem = await perft.check(self.settings, spec, fens, depth)
        except uci.EngineFault as fault:
            return f"Protocol problem: {fault}. Check the UCI handshake and the perft output."
        if problem is None:
            return f"OK: {len(fens)} position(s) at depth {depth} match the reference."
        return f"Mismatch: {problem}"

    async def submit(self, params: dict[str, Any]) -> str:
        hypothesis = str(params.get("hypothesis") or "").strip()
        if len(hypothesis) < 10:
            raise ToolError("Write a real hypothesis: what you changed and what you expect.")
        message = f"exp-{self.experiment_id}: {hypothesis}"[:500]
        sha = await self.sandbox.commit_all(message, self.base_commit)
        if sha is None:
            raise ToolError("Nothing changed in /genome: there is nothing to submit.")
        stat = await self.sandbox.diff_stat(self.base_commit, sha)
        if not stat.get("files"):
            # Commits that end where the base is: judging it would only play the champion
            # against itself for hours.
            raise ToolError("Your tree is identical to the base: change the engine first.")
        await sandbox.archive(self.settings, sha, f"exp-{self.experiment_id}")
        await self.ledger.set_submission(self.experiment_id, hypothesis, sha, stat)
        self._notify("hypothesis", self.experiment_id)
        lesson = str(params.get("lesson_for_previous") or "").strip()
        if lesson and self.previous_experiment_id is not None:
            await self.ledger.set_lesson(self.previous_experiment_id, lesson[:500])
            self._notify("lesson", self.previous_experiment_id)
        self.submitted = sha
        return (
            f"Submitted {sha[:12]} ({stat}). The referee is judging it; you will see the "
            "verdict next session. This session is over: stop now."
        )

    async def experiments(self, params: dict[str, Any]) -> str:
        limit = int(params.get("limit") or 10)
        query = str(params.get("query") or "").strip()
        rows = (
            await self.ledger.search_experiments(query, limit)
            if query
            else await self.ledger.recent_experiments(limit)
        )
        if not rows:
            return "No experiments found."
        lines = []
        for row in rows:
            lines.append(_describe(row, await self.ledger.gates_of(row.id)))
        return "\n".join(lines)

    async def run_job(self, params: dict[str, Any]) -> str:
        action = params.get("action")
        if action == "status":
            jobs = await self.ledger.jobs()
            used, ceiling = await self.jobs.storage()
            storage = (
                f"Job storage: {used:.1f} of {ceiling:g} GB "
                f"({self.settings.job_disk_gb:g} GB per job)."
            )
            if not jobs:
                return f"No jobs yet. {storage}"
            return "\n".join(
                [storage]
                + [
                    f"job {j.id}: {j.status} (exit {j.exit_code}) "
                    f"{j.purpose or '(no purpose)'}: `{j.command[:100]}`"
                    + (f"\n  log: {j.log_tail[-600:]}" if j.log_tail else "")
                    for j in jobs[:5]
                ]
            )
        if action == "delete":
            try:
                freed = await self.jobs.delete(int(params.get("job_id") or 0))
            except (JobError, ValueError) as exc:
                raise ToolError(str(exc)) from exc
            return f"Deleted the files of job {params.get('job_id')}: {freed:.2f} GB freed."
        command = str(params.get("command") or "").strip()
        if not command:
            raise ToolError("start needs a command")
        purpose = " ".join(str(params.get("purpose") or "").split())
        if not purpose:
            raise ToolError("start needs a purpose: one sentence on what the job is for")
        hours = min(float(params.get("hours") or 1.0), 12.0)
        try:
            job_id = await self.jobs.start(
                self.experiment_id, command, purpose[:MAX_PURPOSE], hours
            )
        except JobError as exc:
            raise ToolError(str(exc)) from exc
        return f"Job {job_id} started. Its output will be in /jobs/{job_id}/out."

    async def lichess_losses(self, params: dict[str, Any]) -> str:
        limit = min(max(int(params.get("limit") or 5), 1), 10)
        rows = await lichess.losses(self.ledger, limit=limit)
        if not rows:
            return "No Lichess losses yet."
        head = f"{len(rows)} most recent Lichess loss(es), newest first."
        return "\n\n".join([head, *(_describe_loss(row) for row in rows)])


MAX_PURPOSE = 200  # one sentence, shown on the public site
LOSS_PLIES = 40  # the tail of the game is where the loss happened; the opening costs tokens
MATE_CP = 10000  # how the analysis encodes a forced mate
WORST_KEYS = {"move_number", "move", "eval_before_cp", "eval_after_cp", "fen_before"}


def _pawns(cp: int) -> str:
    if cp >= MATE_CP:
        return "a forced mate for you"
    if cp <= -MATE_CP:
        return "a forced mate against you"
    return f"{cp / 100:+.1f}"


def _describe_loss(row: m.LichessGame) -> str:
    opponent = " ".join(p for p in (row.opponent_title, row.opponent) if p)
    if row.opponent_rating:
        opponent += f" ({row.opponent_rating})"
    plies = row.moves.split()
    kind = "rated" if row.rated else "casual"
    lines = [
        f"Game {row.lichess_id} (gen-{row.generation_id}): you were {row.color} against "
        f"{opponent}, {row.time_control} {kind}, ended ({row.status}) after "
        f"{(len(plies) + 1) // 2} moves."
    ]
    worst = row.analysis or {}
    if worst.keys() >= WORST_KEYS:
        lines.append(
            f"  Worst move: move {worst['move_number']} ({worst['move']}): your evaluation "
            f"went from {_pawns(int(worst['eval_before_cp']))} to "
            f"{_pawns(int(worst['eval_after_cp']))}, position before: {worst['fen_before']}"
        )
    else:
        lines.append("  Worst move: not analysed.")
    if len(plies) > LOSS_PLIES:
        lines.append(
            f"  Moves (UCI, last {LOSS_PLIES} of {len(plies)} plies): ... "
            + " ".join(plies[-LOSS_PLIES:])
        )
    else:
        lines.append(f"  Moves (UCI): {' '.join(plies) or '(none)'}")
    return "\n".join(lines)


def _describe(row: m.Experiment, gates: list[m.GateResult] | Any) -> str:
    head = f"#{row.id} [{row.phase}] {row.status}"
    if row.rejected_at_gate:
        head += f" at {row.rejected_at_gate}"
    details = "; ".join(
        f"{g.gate} {'ok' if g.passed else 'FAILED'} "
        + str({k: v for k, v in g.detail.items() if k not in {"pgn", "log"}})
        for g in gates
    )
    text = f"{head}: {row.hypothesis or '(no submission)'}"
    if details:
        text += f"\n  gates: {details}"
    if row.lesson:
        text += f"\n  lesson: {row.lesson}"
    return text


class ToolRouter:
    """Maps the bearer token of the running sessions to their tools."""

    def __init__(self, notify: Notify | None = None) -> None:
        self._sessions: dict[str, SessionTools] = {}
        self.notify = notify

    def register(self, tools: SessionTools) -> str:
        if tools.notify is None:
            tools.notify = self.notify
        token = secrets.token_urlsafe(24)
        self._sessions[token] = tools
        return token

    def unregister(self, token: str) -> None:
        self._sessions.pop(token, None)

    def app(self) -> FastAPI:
        app = FastAPI(title="darwin tools", docs_url=None, redoc_url=None, openapi_url=None)

        @app.post("/tools/{tool}")
        async def call(
            tool: str, request: Request, authorization: str = Header(default="")
        ) -> dict[str, str]:
            session = self._sessions.get(authorization.removeprefix("Bearer "))
            if session is None:
                raise HTTPException(401, "unknown session")
            params = await request.json()
            try:
                return {
                    "text": await session.call(tool, params if isinstance(params, dict) else {})
                }
            except ToolError as exc:
                raise HTTPException(400, str(exc)) from exc

        return app
