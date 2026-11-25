"""Read-only queries for the API and the dashboard."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from darwin.ledger import commentary
from darwin.ledger import models as m
from darwin.ledger.lichess import performance
from darwin.ledger.store import Ledger


async def generations_with_story(ledger: Ledger) -> list[dict[str, Any]]:
    """Every champion with the hypothesis that won it and how many attempts it took."""
    async with ledger.session() as s:
        gens = (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()
        rows: list[dict[str, Any]] = []
        previous_experiment = 0
        for gen in gens:
            hypothesis, title, tried = None, None, 0
            if gen.experiment_id is not None:
                title = (await commentary.of(s, commentary.TITLE, [gen.experiment_id])).get(
                    gen.experiment_id
                )
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
                    "elo_absolute_error": rating.elo_error if rating else None,
                    "hypothesis": hypothesis,
                    "title": commentary.view(title),
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
        italian = await commentary.of(s, commentary.HYPOTHESIS, [row.id])
        title = await commentary.of(s, commentary.TITLE, [row.id])
    return {
        "id": row.id,
        "phase": row.phase,
        "status": row.status,
        "title": commentary.view(title.get(row.id)),
        "hypothesis": row.hypothesis,
        "hypothesis_it": commentary.italian(italian.get(row.id)),
        "rejected_at_gate": row.rejected_at_gate,
        "lesson": row.lesson,
        "diff_stat": row.diff_stat,
        "progress": row.progress,
        "created_at": row.created_at.isoformat(),
        "gates": [gate_view(g) for g in gates],
        "match": None if match is None else match_view(match),
    }


def gate_view(gate: m.GateResult) -> dict[str, Any]:
    """A gate without its bulky fields (games, build log)."""
    return {
        "gate": gate.gate,
        "passed": gate.passed,
        "detail": {k: v for k, v in gate.detail.items() if k not in {"pgn", "log"}},
    }


def match_view(match: m.Match) -> dict[str, Any]:
    return {
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


async def lichess_summary(
    ledger: Ledger, site: str, account: str, recent: int = 20
) -> dict[str, Any]:
    """The last finished Lichess games, with their commentary, and the performance of every
    generation that played.

    Performance counts every finished game, not only the recent ones.
    """
    async with ledger.session() as s:
        query = select(m.LichessGame).where(m.LichessGame.finished_at.is_not(None))
        rows = (await s.scalars(query.order_by(m.LichessGame.id.desc()))).all()
        texts = await commentary.of(s, commentary.LICHESS_GAME, [g.id for g in rows[:recent]])
    return {
        "profile_url": f"{site.rstrip('/')}/@/{account}/all" if account else None,
        "recent": [
            {
                "lichess_id": g.lichess_id,
                "url": f"{site.rstrip('/')}/{g.lichess_id}",
                "opponent": g.opponent,
                "opponent_rating": g.opponent_rating,
                "opponent_title": g.opponent_title,
                "color": g.color,
                "result": g.result,
                "status": g.status,
                "generation_id": g.generation_id,
                "time_control": g.time_control,
                "finished_at": g.finished_at.isoformat() if g.finished_at else None,
                "commentary": commentary.view(texts.get(g.id)),
            }
            for g in rows[:recent]
        ],
        "performance": performance(rows),
    }


async def jobs_view(ledger: Ledger) -> dict[str, Any]:
    """Long jobs started by the agent: the ones running and the last one that ended."""
    async with ledger.session() as s:
        running = (
            await s.scalars(
                select(m.Job).where(m.Job.status == "running").order_by(m.Job.id.desc())
            )
        ).all()
        last = await s.scalar(
            select(m.Job)
            .where(m.Job.status != "running")
            .order_by(m.Job.finished_at.desc(), m.Job.id.desc())
            .limit(1)
        )
    return {
        "running": [
            {
                "id": j.id,
                "command": j.command,
                "created_at": j.created_at.isoformat(),
                "max_hours": j.max_hours,
            }
            for j in running
        ],
        "last_finished": None
        if last is None
        else {
            "id": last.id,
            "command": last.command,
            "status": last.status,
            "exit_code": last.exit_code,
            "created_at": last.created_at.isoformat(),
            "finished_at": last.finished_at.isoformat() if last.finished_at else None,
            "max_hours": last.max_hours,
        },
    }
