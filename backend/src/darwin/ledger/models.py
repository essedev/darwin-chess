"""Ledger tables, as specified in docs/DATABASE_SCHEMA.md. Append-only: rows are never
deleted; a row changes only to close an open state (`status`, `finished_at`)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from darwin.ledger.base import Base, UtcDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


class Timestamped:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow,
                                                 index=True)  # fmt: skip


class Experiment(Timestamped, Base):
    """One agent session: an iteration (hypothesis, candidate, verdict) or a reflection."""

    __tablename__ = "experiments"

    kind: Mapped[str] = mapped_column(String(16), default="iteration")
    phase: Mapped[str] = mapped_column(String(16))
    base_commit: Mapped[str] = mapped_column(String(40))
    base_generation_id: Mapped[int | None] = mapped_column(ForeignKey("generations.id"))
    trigger: Mapped[str] = mapped_column(String(32))
    hypothesis: Mapped[str | None] = mapped_column(Text)
    candidate_commit: Mapped[str | None] = mapped_column(String(40))
    diff_stat: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    rejected_at_gate: Mapped[str | None] = mapped_column(String(16))
    lesson: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class GateResult(Timestamped, Base):
    __tablename__ = "gate_results"

    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    gate: Mapped[str] = mapped_column(String(16))
    passed: Mapped[bool]
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    duration_ms: Mapped[int]


class Match(Timestamped, Base):
    __tablename__ = "matches"

    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    engine_a: Mapped[str] = mapped_column(String(64))
    engine_b: Mapped[str] = mapped_column(String(64))
    time_control: Mapped[str] = mapped_column(String(32))
    wins: Mapped[int] = mapped_column(default=0)
    draws: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    pentanomial: Mapped[list[int] | None] = mapped_column(JSON)
    elo_diff: Mapped[float | None] = mapped_column(Float)
    elo_error: Mapped[float | None] = mapped_column(Float)
    llr: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str | None] = mapped_column(String(16))
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class Game(Timestamped, Base):
    __tablename__ = "games"

    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    white: Mapped[str] = mapped_column(String(64))
    black: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(8))
    termination: Mapped[str] = mapped_column(String(16))
    pgn: Mapped[str] = mapped_column(Text)


class Generation(Base):
    """A champion. `gen-0` is the empty seed; N >= 1 won its match."""

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"))
    commit_sha: Mapped[str] = mapped_column(String(40), unique=True)
    elo_vs_parent: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utcnow)


class RatingSnapshot(Timestamped, Base):
    __tablename__ = "rating_snapshots"

    generation_id: Mapped[int] = mapped_column(ForeignKey("generations.id"), index=True)
    source: Mapped[str] = mapped_column(String(16))
    elo: Mapped[float] = mapped_column(Float)
    elo_error: Mapped[float | None] = mapped_column(Float)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class LlmCall(Timestamped, Base):
    __tablename__ = "llm_calls"

    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    model: Mapped[str] = mapped_column(String(128))
    input_tokens: Mapped[int] = mapped_column(default=0)
    cached_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


class AgentEvent(Timestamped, Base):
    __tablename__ = "agent_events"

    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class Job(Timestamped, Base):
    """A long CPU-only run started by the agent with `run_job` (self-play, training)."""

    __tablename__ = "jobs"

    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    command: Mapped[str] = mapped_column(Text)
    cpus: Mapped[float] = mapped_column(Float)
    max_hours: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    exit_code: Mapped[int | None]
    log_tail: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
