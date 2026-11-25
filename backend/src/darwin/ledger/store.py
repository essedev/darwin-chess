"""The ledger's only writer API. One process writes (core), the API only reads."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import event, func, or_, select
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from darwin.ledger import models as m
from darwin.referee.judge import Phase, Verdict
from darwin.referee.models import GameRecord


@dataclass(frozen=True)
class LabState:
    phase: Phase
    champion: m.Generation
    base_commit: str  # where the next iteration starts from


def _counts(games: list[GameRecord], name: str) -> tuple[int, int, int]:
    scores = [game.score_for(name) for game in games]
    return scores.count(1.0), scores.count(0.5), scores.count(0.0)


class Ledger:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _sqlite_pragmas)
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessions() as session, session.begin():
            yield session

    # State

    async def seed(self, commit: str) -> m.Generation:
        """Registers gen-0 (the empty seed) once; returns the existing one afterwards."""
        async with self.session() as s:
            existing = await s.get(m.Generation, 0)
            if existing is not None:
                return existing
            gen0 = m.Generation(id=0, commit_sha=commit)
            s.add(gen0)
            return gen0

    async def state(self) -> LabState:
        async with self.session() as s:
            champion = await s.scalar(select(m.Generation).order_by(m.Generation.id.desc()))
            if champion is None:
                raise LookupError("ledger not seeded: no gen-0")
            accepted = await s.scalar(
                select(m.Experiment)
                .where(m.Experiment.status == "accepted")
                .order_by(m.Experiment.id.desc())
            )
        if champion.id >= 1:
            phase = Phase.EVOLUTION
        elif accepted is not None:
            phase = Phase.FIRST_STEPS
        else:
            phase = Phase.GENESIS
        base = accepted.candidate_commit if accepted and accepted.candidate_commit else None
        return LabState(phase, champion, base or champion.commit_sha)

    # Experiments

    async def start_experiment(
        self, *, kind: str, phase: Phase, base_commit: str, base_generation_id: int | None,
        trigger: str,
    ) -> int:  # fmt: skip
        async with self.session() as s:
            row = m.Experiment(kind=kind, phase=phase.value, base_commit=base_commit,
                               base_generation_id=base_generation_id, trigger=trigger)  # fmt: skip
            s.add(row)
            await s.flush()
            return row.id

    async def set_submission(
        self, experiment_id: int, hypothesis: str, commit: str, diff_stat: dict[str, Any]
    ) -> None:
        async with self.session() as s:
            row = await s.get_one(m.Experiment, experiment_id)
            row.hypothesis, row.candidate_commit, row.diff_stat = hypothesis, commit, diff_stat
            row.status = "judging"

    async def finish_experiment(
        self, experiment_id: int, status: str, *, error: str | None = None
    ) -> None:
        async with self.session() as s:
            row = await s.get_one(m.Experiment, experiment_id)
            row.status, row.error, row.finished_at = status, error, m.utcnow()

    async def set_lesson(self, experiment_id: int, lesson: str) -> None:
        async with self.session() as s:
            (await s.get_one(m.Experiment, experiment_id)).lesson = lesson

    async def record_verdict(self, experiment_id: int, verdict: Verdict) -> m.Generation | None:
        """Stores gates, match and games; promotes a new generation when a match is won."""
        async with self.session() as s:
            experiment = await s.get_one(m.Experiment, experiment_id)
            for gate in verdict.gates:
                s.add(m.GateResult(experiment_id=experiment_id, gate=gate.gate.value,
                                   passed=gate.passed, detail=gate.detail,
                                   duration_ms=gate.duration_ms))  # fmt: skip
            failed = next((gate for gate in verdict.gates if not gate.passed), None)
            experiment.rejected_at_gate = failed.gate.value if failed else None
            experiment.status = "accepted" if verdict.accepted else "rejected"
            experiment.finished_at = m.utcnow()
            promoted = None
            if verdict.match is not None:
                result = verdict.match
                wins, draws, losses = _counts(result.games, "candidate")
                match = m.Match(
                    experiment_id=experiment_id, kind="sprt",
                    engine_a=experiment.candidate_commit or "candidate", engine_b=result.opponent,
                    time_control=result.tc, wins=wins, draws=draws, losses=losses,
                    pentanomial=result.penta, elo_diff=result.elo, elo_error=result.elo_error,
                    llr=result.llr, verdict=result.verdict.value, finished_at=m.utcnow(),
                )  # fmt: skip
                s.add(match)
                await s.flush()
                for game in result.games:
                    s.add(m.Game(match_id=match.id, white=game.white, black=game.black,
                                 result=game.result, termination=game.termination.value,
                                 pgn=game.pgn))  # fmt: skip
                if verdict.accepted and experiment.candidate_commit:
                    top = await s.scalar(select(func.max(m.Generation.id)))
                    promoted = m.Generation(id=(top or 0) + 1, experiment_id=experiment_id,
                                            commit_sha=experiment.candidate_commit,
                                            elo_vs_parent=result.elo)  # fmt: skip
                    s.add(promoted)
            return promoted

    async def recent_experiments(self, limit: int) -> Sequence[m.Experiment]:
        async with self.session() as s:
            query = select(m.Experiment).where(m.Experiment.kind == "iteration")
            rows = await s.scalars(query.order_by(m.Experiment.id.desc()).limit(limit))
            return rows.all()

    async def search_experiments(self, text: str, limit: int) -> Sequence[m.Experiment]:
        pattern = f"%{text}%"
        async with self.session() as s:
            query = select(m.Experiment).where(
                or_(m.Experiment.hypothesis.ilike(pattern), m.Experiment.lesson.ilike(pattern))
            )
            return (await s.scalars(query.order_by(m.Experiment.id.desc()).limit(limit))).all()

    async def gates_of(self, experiment_id: int) -> Sequence[m.GateResult]:
        async with self.session() as s:
            query = select(m.GateResult).where(m.GateResult.experiment_id == experiment_id)
            return (await s.scalars(query.order_by(m.GateResult.id))).all()

    async def generations(self) -> Sequence[m.Generation]:
        async with self.session() as s:
            return (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()

    # Agent activity and spend

    async def add_event(self, experiment_id: int, kind: str, payload: dict[str, Any]) -> int:
        async with self.session() as s:
            row = m.AgentEvent(experiment_id=experiment_id, kind=kind, payload=payload)
            s.add(row)
            await s.flush()
            return row.id

    async def add_llm_call(
        self, experiment_id: int, model: str, *, input_tokens: int, cached_tokens: int,
        output_tokens: int, cost_usd: float,
    ) -> None:  # fmt: skip
        async with self.session() as s:
            s.add(m.LlmCall(experiment_id=experiment_id, model=model, input_tokens=input_tokens,
                            cached_tokens=cached_tokens, output_tokens=output_tokens,
                            cost_usd=cost_usd))  # fmt: skip

    async def spend_since(self, since: datetime) -> float:
        async with self.session() as s:
            total = await s.scalar(
                select(func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0)).where(
                    m.LlmCall.created_at >= since
                )
            )
            return float(total or 0.0)

    async def spend_of(self, experiment_id: int) -> float:
        async with self.session() as s:
            total = await s.scalar(
                select(func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0)).where(
                    m.LlmCall.experiment_id == experiment_id
                )
            )
            return float(total or 0.0)

    # Jobs

    async def start_job(self, experiment_id: int, command: str, cpus: float,
                        max_hours: float) -> int:  # fmt: skip
        async with self.session() as s:
            row = m.Job(experiment_id=experiment_id, command=command, cpus=cpus,
                        max_hours=max_hours)  # fmt: skip
            s.add(row)
            await s.flush()
            return row.id

    async def finish_job(self, job_id: int, status: str, exit_code: int | None,
                         log_tail: str) -> None:  # fmt: skip
        async with self.session() as s:
            row = await s.get_one(m.Job, job_id)
            row.status, row.exit_code, row.log_tail = status, exit_code, log_tail
            row.finished_at = m.utcnow()

    async def jobs(self, *, running_only: bool = False) -> Sequence[m.Job]:
        async with self.session() as s:
            query = select(m.Job).order_by(m.Job.id.desc())
            if running_only:
                query = query.where(m.Job.status == "running")
            return (await s.scalars(query)).all()


def _sqlite_pragmas(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")  # the API reads while core writes
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
