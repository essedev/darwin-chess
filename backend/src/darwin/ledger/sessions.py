"""One agent session as its page reads it: the experiment, its events in order, its outcome
and the sessions on either side. Read-only."""

from typing import Any

from sqlalchemy import func, select

from darwin.ledger import commentary
from darwin.ledger import models as m
from darwin.ledger.queries import event_view, gate_view, match_view
from darwin.ledger.store import Ledger

# A session stops at 80 tool calls, so it holds a few hundred events at most; the cap only
# bounds the answer if that limit ever moves. Every payload is already capped on write.
MAX_EVENTS = 600


async def session_view(ledger: Ledger, experiment_id: int) -> dict[str, Any] | None:
    """The session `experiment_id`, or None when there is no such experiment."""
    async with ledger.session() as s:
        e = await s.get(m.Experiment, experiment_id)
        if e is None:
            return None
        rows = (
            await s.scalars(
                select(m.AgentEvent)
                .where(m.AgentEvent.experiment_id == experiment_id)
                .order_by(m.AgentEvent.id)
                .limit(MAX_EVENTS + 1)
            )
        ).all()
        thoughts = await commentary.of(
            s, commentary.THOUGHT, [r.id for r in rows if r.kind == "thought"]
        )
        title = await commentary.of(s, commentary.TITLE, [e.id])
        hypothesis_it = await commentary.of(s, commentary.HYPOTHESIS, [e.id])
        cost = await s.scalar(
            select(func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0)).where(
                m.LlmCall.experiment_id == e.id
            )
        )
        generation = await s.scalar(
            select(m.Generation.id).where(m.Generation.experiment_id == e.id)
        )
        gates = (
            await s.scalars(
                select(m.GateResult)
                .where(m.GateResult.experiment_id == e.id)
                .order_by(m.GateResult.id)
            )
        ).all()
        match = await s.scalar(
            select(m.Match).where(m.Match.experiment_id == e.id).order_by(m.Match.id.desc())
        )
        previous = await s.scalar(select(func.max(m.Experiment.id)).where(m.Experiment.id < e.id))
        following = await s.scalar(select(func.min(m.Experiment.id)).where(m.Experiment.id > e.id))
    return {
        "id": e.id,
        "kind": e.kind,
        "phase": e.phase,
        "status": e.status,
        "trigger": e.trigger,
        "base_generation_id": e.base_generation_id,
        "generation_id": generation,
        "title": commentary.view(title.get(e.id)),
        "hypothesis": e.hypothesis,
        "hypothesis_it": commentary.italian(hypothesis_it.get(e.id)),
        "rejected_at_gate": e.rejected_at_gate,
        "candidate_commit": e.candidate_commit,
        "created_at": e.created_at.isoformat(),
        "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        "cost_usd": float(cost or 0.0),
        "gates": [gate_view(g) for g in gates],
        "match": None if match is None else match_view(match),
        "events": [event_view(r, thoughts.get(r.id)) for r in rows[:MAX_EVENTS]],
        "truncated": len(rows) > MAX_EVENTS,
        "previous": previous,
        "next": following,
    }
