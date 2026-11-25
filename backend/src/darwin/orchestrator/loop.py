"""The orchestrator: agent sessions and the referee, paced by events and the budget.

- One agent session at a time. A new one starts when the budget quota allows it and the
  referee is not already holding a queued candidate (one judging, at most one waiting).
- The referee judges candidates one by one. A candidate whose base was overtaken by a new
  champion is replayed on top of it first; if that conflicts it is stale.
- Every few iterations, the session is a reflection instead.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import uvicorn

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import budget, sandbox
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.session import SessionRunner
from darwin.orchestrator.tools import ToolRouter
from darwin.referee import engines
from darwin.referee.build import build_gate
from darwin.referee.errors import RefereeError
from darwin.referee.judge import Phase, judge
from darwin.referee.models import Binary
from darwin.referee.rating import rate

log = logging.getLogger(__name__)

SEED_MEMORY = Path(__file__).resolve().parents[4] / "seed"
RETRY_AFTER_FAILURE_S = 120.0
MAX_WAITING = 1
RATING_PAIRS = 20
RATING_TC = "8+0.08"


class Orchestrator:
    def __init__(self, settings: Settings, ledger: Ledger) -> None:
        self.settings = settings
        self.ledger = ledger
        self.router = ToolRouter()
        self.jobs = Jobs(settings, ledger, self._job_done)
        self.sessions = SessionRunner(settings, ledger, self.router, self.jobs)
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.judging = 0
        self.wake = asyncio.Event()
        self.triggers: list[str] = ["start"]
        self.iterations_since_reflection = 0

    # Setup

    async def prepare(self) -> None:
        gen0 = await sandbox.init_mirror(self.settings)
        await self.ledger.seed(gen0)
        memory = self.settings.data_dir / "agent" / "memory"
        memory.mkdir(parents=True, exist_ok=True)
        for name in ("NOTES.md", "STRATEGY.md"):
            if not (memory / name).exists():
                (memory / name).write_text((SEED_MEMORY / name).read_text())
        await self.jobs.recover()
        for row in await self.ledger.unfinished_experiments():
            if row.status == "judging" and row.candidate_commit:
                self.queue.put_nowait(row.id)  # judged again after a restart
            else:
                await self.ledger.finish_experiment(row.id, "error", error="orchestrator restarted")

    async def serve_tools(self) -> None:
        config = uvicorn.Config(
            self.router.app(), host="127.0.0.1", port=self.settings.tools_port, log_level="warning"
        )
        await uvicorn.Server(config).serve()

    # Events

    async def _job_done(self, job_id: int) -> None:
        self._trigger(f"job_done:{job_id}")

    def _trigger(self, name: str) -> None:
        self.triggers.append(name)
        self.wake.set()

    # Agent side

    async def run(self, *, max_sessions: int | None = None) -> None:
        await self.prepare()
        servers = [asyncio.create_task(self.serve_tools()), asyncio.create_task(self.judge_loop())]
        try:
            await self.agent_loop(max_sessions)
            if max_sessions is not None:  # test runs: wait for the last verdict
                await self.queue.join()
        finally:
            for task in servers:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def agent_loop(self, max_sessions: int | None) -> None:
        sessions = 0
        while max_sessions is None or sessions < max_sessions:
            await self._wait_for_room()
            await self._wait_for_budget()
            trigger = self.triggers.pop(0) if self.triggers else "continue"
            reflect = self.iterations_since_reflection >= self.settings.reflection_every
            outcome = await self.sessions.run(
                kind="reflection" if reflect else "iteration",
                trigger=trigger,
                state=await self.ledger.state(),
            )
            sessions += 1
            if reflect:
                self.iterations_since_reflection = 0
            else:
                self.iterations_since_reflection += 1
            if outcome.submitted is not None:
                self.queue.put_nowait(outcome.experiment_id)
            elif outcome.status in {"error", "budget_stop", "abandoned"} and (
                max_sessions is None or sessions < max_sessions
            ):
                await asyncio.sleep(RETRY_AFTER_FAILURE_S)

    async def _wait_for_room(self) -> None:
        while self.queue.qsize() + self.judging > MAX_WAITING:
            self.wake.clear()
            await self.wake.wait()

    async def _wait_for_budget(self) -> None:
        s = self.settings
        while True:
            now = datetime.now(UTC)
            spent = await self.ledger.spend_since(budget.day_start(now))
            delay = budget.wait_before_session(now, spent, s.daily_budget_usd, s.session_max_usd)
            if delay.total_seconds() <= 0:
                return
            log.info("budget: %.3f $ spent today, next session in %s", spent, delay)
            await asyncio.sleep(min(delay.total_seconds(), 600))

    # Referee side

    async def judge_loop(self) -> None:
        while True:
            experiment_id = await self.queue.get()
            self.judging += 1
            try:
                await self.judge_one(experiment_id)
            except Exception as exc:
                log.exception("judging %s failed", experiment_id)
                await self.ledger.finish_experiment(experiment_id, "error", error=str(exc)[-4000:])
            finally:
                self.judging -= 1
                self.queue.task_done()
                self._trigger(f"verdict:{experiment_id}")

    async def judge_one(self, experiment_id: int) -> None:
        s = self.settings
        row = await self.ledger.experiment(experiment_id)
        state = await self.ledger.state()
        assert row.candidate_commit is not None
        commit = row.candidate_commit
        if row.base_commit != state.base_commit:
            rebased = await sandbox.rebase(
                s, commit, row.base_commit, state.base_commit, f"exp-{experiment_id}-rebased"
            )
            if rebased is None:
                await self.ledger.finish_experiment(
                    experiment_id, "stale", error="conflicts with the new base"
                )
                return
            await self.ledger.rebased(experiment_id, rebased)
            commit = rebased
        champion = None
        if state.phase is Phase.EVOLUTION:
            gate, champion = await build_gate(s, state.champion.commit_sha)
            if champion is None:
                raise RefereeError(f"the champion does not build: {gate.detail}")
        await self.ledger.add_event(
            experiment_id, "status", {"state": "judging", "phase": state.phase.value}
        )
        verdict = await judge(s, commit, state.phase, champion=champion, seed=experiment_id)
        promoted = await self.ledger.record_verdict(experiment_id, verdict)
        if promoted is not None:
            done = await sandbox.helper(
                s, sandbox.update_ref_script(f"gen-{promoted.id}", promoted.commit_sha)
            )
            if done.code != 0:
                raise RefereeError(f"cannot tag gen-{promoted.id}: {done.output}")
            log.info("gen-%d: %s", promoted.id, promoted.commit_sha[:12])
            if verdict.binary is not None:
                await self.rate(promoted.id, verdict.binary, experiment_id)

    async def rate(self, generation_id: int, binary: Binary, seed: int) -> None:
        """Absolute Elo of a new champion against Stockfish. Informative only: a failure here
        is logged and never undoes the promotion."""
        spec = engines.candidate(self.settings, binary, name=f"gen-{generation_id}")
        try:
            rating = await rate(self.settings, spec, pairs=RATING_PAIRS, tc=RATING_TC, seed=seed)
        except RefereeError:
            log.exception("rating gen-%d failed", generation_id)
            return
        if rating.elo is not None:
            await self.ledger.add_rating(
                generation_id, "anchors", rating.elo, rating.error, rating.detail()
            )
        else:
            log.info("gen-%d is below the anchor ladder", generation_id)
