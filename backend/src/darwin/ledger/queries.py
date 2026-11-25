"""Read-only queries for the API and the dashboard."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from darwin.ledger import models as m
from darwin.ledger.store import Ledger


async def generations_with_story(ledger: Ledger) -> list[dict[str, Any]]:
    """Every champion with the hypothesis that won it and how many attempts it took."""
    async with ledger.session() as s:
        gens = (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()
        rows: list[dict[str, Any]] = []
        previous_experiment = 0
        for gen in gens:
            hypothesis, tried = None, 0
            if gen.experiment_id is not None:
                winner = await s.get_one(m.Experiment, gen.experiment_id)
                hypothesis = winner.hypothesis
                tried = (
                    await s.scalar(
                        select(func.count(m.Experiment.id)).where(
                            m.Experiment.kind == "iteration",
                            m.Experiment.id > previous_experiment,
                            m.Experiment.id <= gen.experiment_id,
                        )
                    )
                    or 0
                )
                previous_experiment = gen.experiment_id
            rating = await s.scalar(
                select(m.RatingSnapshot)
                .where(m.RatingSnapshot.generation_id == gen.id)
                .where(m.RatingSnapshot.source == "anchors")
                .order_by(m.RatingSnapshot.id.desc())
            )
            rows.append(
                {
                    "id": gen.id,
                    "commit": gen.commit_sha,
                    "elo_vs_parent": gen.elo_vs_parent,
                    "elo_absolute": rating.elo if rating else None,
                    "hypothesis": hypothesis,
                    "tried": tried,
                    "created_at": gen.created_at.isoformat(),
                }
            )
        return rows


async def experiment_counts(ledger: Ledger) -> dict[str, int]:
    async with ledger.session() as s:
        query = select(m.Experiment.status, func.count()).where(m.Experiment.kind == "iteration")
        result = await s.execute(query.group_by(m.Experiment.status))
        counts = {status: int(count) for status, count in result}
    return {"total": sum(counts.values()), **counts}


async def latest_experiments(ledger: Ledger, limit: int) -> Sequence[m.Experiment]:
    async with ledger.session() as s:
        query = select(m.Experiment).where(m.Experiment.kind == "iteration")
        return (await s.scalars(query.order_by(m.Experiment.id.desc()).limit(limit))).all()


async def experiment_view(ledger: Ledger, row: m.Experiment) -> dict[str, Any]:
    async with ledger.session() as s:
        gates = (
            await s.scalars(
                select(m.GateResult)
                .where(m.GateResult.experiment_id == row.id)
                .order_by(m.GateResult.id)
            )
        ).all()
        match = await s.scalar(
            select(m.Match).where(m.Match.experiment_id == row.id).order_by(m.Match.id.desc())
        )
    return {
        "id": row.id,
        "phase": row.phase,
        "status": row.status,
        "hypothesis": row.hypothesis,
        "rejected_at_gate": row.rejected_at_gate,
        "lesson": row.lesson,
        "diff_stat": row.diff_stat,
        "created_at": row.created_at.isoformat(),
        "gates": [
            {
                "gate": g.gate,
                "passed": g.passed,
                "detail": {k: v for k, v in g.detail.items() if k not in {"pgn", "log"}},
            }
            for g in gates
        ],
        "match": None
        if match is None
        else {
            "opponent": match.engine_b,
            "wins": match.wins,
            "draws": match.draws,
            "losses": match.losses,
            "pentanomial": match.pentanomial,
            "elo": match.elo_diff,
            "elo_error": match.elo_error,
            "llr": match.llr,
            "verdict": match.verdict,
            "time_control": match.time_control,
        },
    }


async def spend(ledger: Ledger, since: datetime) -> dict[str, Any]:
    async with ledger.session() as s:
        total = await s.scalar(
            select(func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0)).where(
                m.LlmCall.created_at >= since
            )
        )
        sessions = await s.scalar(
            select(func.count(m.Experiment.id)).where(m.Experiment.created_at >= since)
        )
    return {"usd": float(total or 0.0), "sessions": int(sessions or 0)}


async def events_after(ledger: Ledger, after_id: int, limit: int = 200) -> list[dict[str, Any]]:
    async with ledger.session() as s:
        query = select(m.AgentEvent).where(m.AgentEvent.id > after_id)
        rows = (await s.scalars(query.order_by(m.AgentEvent.id).limit(limit))).all()
    return [
        {
            "id": e.id,
            "experiment_id": e.experiment_id,
            "kind": e.kind,
            "payload": e.payload,
            "at": e.created_at.isoformat(),
        }
        for e in rows
    ]


async def last_event_id(ledger: Ledger) -> int:
    async with ledger.session() as s:
        return int(await s.scalar(select(func.coalesce(func.max(m.AgentEvent.id), 0))) or 0)


async def recent_events(ledger: Ledger, limit: int) -> list[dict[str, Any]]:
    start = max(0, await last_event_id(ledger) - limit)
    return await events_after(ledger, start, limit)
