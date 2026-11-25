"""Read-only history for the dashboard: every generation, every experiment, the lab's totals."""

from bisect import bisect_right
from collections.abc import Sequence
from itertools import accumulate
from typing import Any

from sqlalchemy import func, select

from darwin.ledger import commentary
from darwin.ledger import models as m
from darwin.ledger.lichess import performance
from darwin.ledger.queries import gate_view, match_view
from darwin.ledger.store import Ledger


async def generations_detail(ledger: Ledger) -> list[dict[str, Any]]:
    """Every champion, newest first, with the experiment that won it and its ratings."""
    async with ledger.session() as s:
        gens = (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()
        winners = [g.experiment_id for g in gens if g.experiment_id is not None]
        experiments = {
            e.id: e
            for e in (
                await s.scalars(select(m.Experiment).where(m.Experiment.id.in_(winners)))
            ).all()
        }
        iterations = (
            await s.scalars(
                select(m.Experiment.id)
                .where(m.Experiment.kind == "iteration")
                .order_by(m.Experiment.id)
            )
        ).all()
        snapshots = (
            await s.scalars(
                select(m.RatingSnapshot)
                .where(m.RatingSnapshot.source.in_(("anchors", "anchors_below")))
                .order_by(m.RatingSnapshot.id)
            )
        ).all()
        games = (
            await s.scalars(select(m.LichessGame).where(m.LichessGame.finished_at.is_not(None)))
        ).all()
        hypotheses_it = await commentary.of(s, commentary.HYPOTHESIS, winners)
        lessons_it = await commentary.of(s, commentary.LESSON, winners)
        titles = await commentary.of(s, commentary.TITLE, winners)
    lichess = performance(games)
    anchors: dict[int, m.RatingSnapshot] = {}
    below: set[int] = set()
    for snap in snapshots:  # ascending: the latest "anchors" rating wins
        if snap.source == "anchors":
            anchors[snap.generation_id] = snap
        else:
            below.add(snap.generation_id)
    rows: list[dict[str, Any]] = []
    parent: str | None = None
    previous_experiment = 0
    for gen in gens:
        winner = experiments.get(gen.experiment_id) if gen.experiment_id is not None else None
        tried = 0
        if gen.experiment_id is not None:
            tried = bisect_right(iterations, gen.experiment_id) - bisect_right(
                iterations, previous_experiment
            )
            previous_experiment = gen.experiment_id
        rows.append(
            {
                "id": gen.id,
                "commit": gen.commit_sha,
                "parent_commit": parent,
                "created_at": gen.created_at.isoformat(),
                "elo_vs_parent": gen.elo_vs_parent,
                "elo_absolute": anchors[gen.id].elo if gen.id in anchors else None,
                "elo_absolute_error": anchors[gen.id].elo_error if gen.id in anchors else None,
                "below_ladder": gen.id in below and gen.id not in anchors,
                "experiment_id": gen.experiment_id,
                "title": commentary.view(titles.get(winner.id)) if winner else None,
                "hypothesis": winner.hypothesis if winner else None,
                "hypothesis_it": commentary.italian(hypotheses_it.get(winner.id))
                if winner
                else None,
                "lesson": winner.lesson if winner else None,
                "lesson_it": commentary.italian(lessons_it.get(winner.id)) if winner else None,
                "tried": tried,
                "diff_stat": winner.diff_stat if winner else None,
                "lichess": lichess.get(gen.id),
            }
        )
        parent = gen.commit_sha
    return rows[::-1]


async def experiments_page(
    ledger: Ledger, limit: int, before_id: int | None, statuses: Sequence[str] = ()
) -> dict[str, Any]:
    """Experiments of any kind, newest first, `limit` at a time below `before_id`, only with
    one of `statuses` when given; `counts` are per status over every experiment."""
    async with ledger.session() as s:
        counts = {
            status: int(n)
            for status, n in await s.execute(
                select(m.Experiment.status, func.count()).group_by(m.Experiment.status)
            )
        }
        query = select(m.Experiment)
        if statuses:
            query = query.where(m.Experiment.status.in_(statuses))
        if before_id is not None:
            query = query.where(m.Experiment.id < before_id)
        rows = (await s.scalars(query.order_by(m.Experiment.id.desc()).limit(limit + 1))).all()
        more = len(rows) > limit
        rows = rows[:limit]
        ids = [r.id for r in rows]
        gates = (
            await s.scalars(
                select(m.GateResult)
                .where(m.GateResult.experiment_id.in_(ids))
                .order_by(m.GateResult.id)
            )
        ).all()
        matches = (
            await s.scalars(
                select(m.Match).where(m.Match.experiment_id.in_(ids)).order_by(m.Match.id)
            )
        ).all()
        costs = await s.execute(
            select(m.LlmCall.experiment_id, func.sum(m.LlmCall.cost_usd))
            .where(m.LlmCall.experiment_id.in_(ids))
            .group_by(m.LlmCall.experiment_id)
        )
        cost_of = {exp_id: float(usd or 0.0) for exp_id, usd in costs}
        hypotheses_it = await commentary.of(s, commentary.HYPOTHESIS, ids)
        lessons_it = await commentary.of(s, commentary.LESSON, ids)
        titles = await commentary.of(s, commentary.TITLE, ids)
    gates_of: dict[int, list[dict[str, Any]]] = {}
    for gate in gates:
        gates_of.setdefault(gate.experiment_id, []).append(gate_view(gate))
    match_of = {x.experiment_id: match_view(x) for x in matches}  # ascending: the latest wins
    items = [
        {
            "id": e.id,
            "kind": e.kind,
            "phase": e.phase,
            "status": e.status,
            "trigger": e.trigger,
            "title": commentary.view(titles.get(e.id)),
            "hypothesis": e.hypothesis,
            "hypothesis_it": commentary.italian(hypotheses_it.get(e.id)),
            "lesson": e.lesson,
            "lesson_it": commentary.italian(lessons_it.get(e.id)),
            "rejected_at_gate": e.rejected_at_gate,
            "created_at": e.created_at.isoformat(),
            "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            "base_commit": e.base_commit,
            "candidate_commit": e.candidate_commit,
            "cost_usd": cost_of.get(e.id, 0.0),
            "gates": gates_of.get(e.id, []),
            "match": match_of.get(e.id),
        }
        for e in rows
    ]
    return {
        "items": items,
        "next_before_id": rows[-1].id if more else None,
        "counts": {"total": sum(counts.values()), **counts},
    }


async def recent_matches(ledger: Ledger, limit: int) -> list[dict[str, Any]]:
    """The last matches the referee recorded, newest first, with the hypothesis they judged
    (and its Italian) and their commentary."""
    async with ledger.session() as s:
        rows = (await s.scalars(select(m.Match).order_by(m.Match.id.desc()).limit(limit))).all()
        exp_ids = [r.experiment_id for r in rows if r.experiment_id is not None]
        experiments = {
            e.id: e
            for e in (
                await s.scalars(select(m.Experiment).where(m.Experiment.id.in_(exp_ids)))
            ).all()
        }
        hypotheses_it = await commentary.of(s, commentary.HYPOTHESIS, exp_ids)
        titles = await commentary.of(s, commentary.TITLE, exp_ids)
        texts = await commentary.of(s, commentary.MATCH, [r.id for r in rows])
    items = []
    for row in rows:
        exp = experiments.get(row.experiment_id) if row.experiment_id is not None else None
        items.append(
            {
                "id": row.id,
                "experiment_id": row.experiment_id,
                "kind": row.kind,
                "opponent": row.engine_b,
                "wins": row.wins,
                "draws": row.draws,
                "losses": row.losses,
                "pentanomial": row.pentanomial,
                "elo": row.elo_diff,
                "elo_error": row.elo_error,
                "verdict": row.verdict,
                "time_control": row.time_control,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "title": commentary.view(titles.get(exp.id)) if exp else None,
                "hypothesis_en": exp.hypothesis if exp else None,
                "hypothesis_it": commentary.italian(hypotheses_it.get(exp.id)) if exp else None,
                "commentary": commentary.view(texts.get(row.id)),
            }
        )
    return items


async def lab_summary(ledger: Ledger) -> dict[str, Any]:
    """When the lab started, what it has cost and done, and the spend behind each champion."""
    async with ledger.session() as s:
        gen0 = await s.get(m.Generation, 0)
        llm = (
            await s.execute(
                select(
                    func.coalesce(func.sum(m.LlmCall.cost_usd), 0.0),
                    func.count(m.LlmCall.id),
                    func.coalesce(func.sum(m.LlmCall.input_tokens), 0),
                    func.coalesce(func.sum(m.LlmCall.cached_tokens), 0),
                    func.coalesce(func.sum(m.LlmCall.output_tokens), 0),
                )
            )
        ).one()
        by_kind_status = (
            await s.execute(
                select(m.Experiment.kind, m.Experiment.status, func.count()).group_by(
                    m.Experiment.kind, m.Experiment.status
                )
            )
        ).all()
        lichess_games = await s.scalar(
            select(func.count(m.LichessGame.id)).where(m.LichessGame.finished_at.is_not(None))
        )
        spend_rows = (
            await s.execute(
                select(m.LlmCall.experiment_id, func.sum(m.LlmCall.cost_usd))
                .group_by(m.LlmCall.experiment_id)
                .order_by(m.LlmCall.experiment_id)
            )
        ).all()
        gens = (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()
    counts = [(kind, status, int(n)) for kind, status, n in by_kind_status]
    totals = {
        "spend_usd": float(llm[0]),
        "sessions": sum(n for _, _, n in counts),
        "iterations": sum(n for kind, _, n in counts if kind == "iteration"),
        "accepted": sum(n for _, status, n in counts if status == "accepted"),
        "rejected": sum(n for _, status, n in counts if status == "rejected"),
        "llm_calls": int(llm[1]),
        "input_tokens": int(llm[2]),
        "cached_tokens": int(llm[3]),
        "output_tokens": int(llm[4]),
        "lichess_games": int(lichess_games or 0),
    }
    # Spend of the experiments in (previous winner, this winner], by prefix sums.
    spend_ids = [exp_id for exp_id, _ in spend_rows]
    prefix = [0.0, *accumulate(float(usd or 0.0) for _, usd in spend_rows)]

    def spent_up_to(experiment_id: int) -> float:
        return prefix[bisect_right(spend_ids, experiment_id)]

    per_generation: list[dict[str, Any]] = []
    previous = 0
    for gen in gens:
        if gen.experiment_id is None:
            continue
        if gen.id > 0:
            usd = spent_up_to(gen.experiment_id) - spent_up_to(previous)
            per_generation.append({"generation": gen.id, "usd": round(usd, 6)})
        previous = gen.experiment_id
    return {
        "started_at": gen0.created_at.isoformat() if gen0 else None,
        "totals": totals,
        "cost_per_generation": per_generation,
    }


async def generation_of(ledger: Ledger, commit: str) -> int | None:
    """The generation whose champion is `commit`, if any."""
    async with ledger.session() as s:
        return await s.scalar(select(m.Generation.id).where(m.Generation.commit_sha == commit))


async def experiment_commits(ledger: Ledger, experiment_id: int) -> tuple[str, str | None] | None:
    """An experiment's base and candidate commits, or None when there is no such experiment."""
    async with ledger.session() as s:
        row = await s.get(m.Experiment, experiment_id)
        return None if row is None else (row.base_commit, row.candidate_commit)
