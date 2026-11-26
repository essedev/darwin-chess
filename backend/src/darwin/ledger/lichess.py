"""Ledger writes and reads for the Lichess bot."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from darwin.ledger import models as m
from darwin.ledger.store import Ledger


async def start_game(
    ledger: Ledger,
    *,
    lichess_id: str,
    generation_id: int,
    color: str,
    opponent: str,
    opponent_rating: int | None,
    opponent_title: str | None,
    rated: bool,
    time_control: str,
) -> None:
    async with ledger.session() as s:
        exists = await s.scalar(select(m.LichessGame).where(m.LichessGame.lichess_id == lichess_id))
        if exists is None:  # the game stream can restart after a dropped connection
            s.add(
                m.LichessGame(
                    lichess_id=lichess_id,
                    generation_id=generation_id,
                    color=color,
                    opponent=opponent,
                    opponent_rating=opponent_rating,
                    opponent_title=opponent_title,
                    rated=rated,
                    time_control=time_control,
                )
            )


async def finish_game(
    ledger: Ledger,
    lichess_id: str,
    *,
    status: str,
    result: str,
    moves: str,
    rating_after: int | None,
) -> int:
    async with ledger.session() as s:
        row = await s.scalar(select(m.LichessGame).where(m.LichessGame.lichess_id == lichess_id))
        if row is None:
            raise LookupError(lichess_id)
        row.status, row.result, row.moves = status, result, moves
        row.rating_after, row.finished_at = rating_after, m.utcnow()
        return row.id


async def set_analysis(ledger: Ledger, game_id: int, analysis: dict[str, Any]) -> None:
    async with ledger.session() as s:
        (await s.get_one(m.LichessGame, game_id)).analysis = analysis


async def set_evals(ledger: Ledger, game_id: int, evals: list[int]) -> None:
    async with ledger.session() as s:
        (await s.get_one(m.LichessGame, game_id)).evals = evals


async def losses(
    ledger: Ledger, *, since: datetime | None = None, limit: int = 10
) -> Sequence[m.LichessGame]:
    async with ledger.session() as s:
        query = select(m.LichessGame).where(m.LichessGame.result == "loss")
        if since is not None:
            query = query.where(m.LichessGame.finished_at >= since)
        return (await s.scalars(query.order_by(m.LichessGame.id.desc()).limit(limit))).all()


async def games(ledger: Ledger, limit: int = 200) -> Sequence[m.LichessGame]:
    async with ledger.session() as s:
        query = select(m.LichessGame).where(m.LichessGame.finished_at.is_not(None))
        return (await s.scalars(query.order_by(m.LichessGame.id.desc()).limit(limit))).all()


def performance(rows: Sequence[m.LichessGame]) -> dict[int, dict[str, Any]]:
    """Per generation: games, score and performance rating (average opponent rating plus
    400 times wins minus losses over games, the usual linear approximation)."""
    by_gen: dict[int, list[m.LichessGame]] = {}
    for row in rows:
        if row.result in {"win", "loss", "draw"} and row.opponent_rating:
            by_gen.setdefault(row.generation_id, []).append(row)
    out: dict[int, dict[str, Any]] = {}
    for gen, played in by_gen.items():
        wins = sum(r.result == "win" for r in played)
        losses_ = sum(r.result == "loss" for r in played)
        draws = len(played) - wins - losses_
        avg = sum(r.opponent_rating or 0 for r in played) / len(played)
        out[gen] = {
            "games": len(played),
            "wins": wins,
            "draws": draws,
            "losses": losses_,
            "performance": round(avg + 400 * (wins - losses_) / len(played)),
        }
    return out


async def record_challenge(ledger: Ledger, opponent: str, outcome: str) -> None:
    async with ledger.session() as s:
        s.add(m.LichessChallenge(opponent=opponent, outcome=outcome))


async def challenges_since(ledger: Ledger, since: datetime) -> Sequence[datetime]:
    """When each challenge Lichess counted was sent, oldest first. A challenge answered 429
    was not accepted, so it is left out."""
    async with ledger.session() as s:
        rows = await s.scalars(
            select(m.LichessChallenge.created_at)
            .where(m.LichessChallenge.created_at >= since)
            .where(m.LichessChallenge.outcome != "rate_limited")
            .order_by(m.LichessChallenge.created_at)
        )
        return rows.all()


async def bot_games_since(ledger: Ledger, since: datetime) -> int:
    async with ledger.session() as s:
        count = await s.scalar(
            select(func.count(m.LichessGame.id))
            .where(m.LichessGame.created_at >= since)
            .where(m.LichessGame.opponent_title == "BOT")
        )
        return int(count or 0)
