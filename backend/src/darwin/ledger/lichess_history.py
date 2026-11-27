"""Read-only history of the bot's Lichess games for the public site: a page of the list and
one game move by move, both with Stockfish's evaluations judged by `game_review`.

Only finished games with a result count: an aborted game has nothing to show.
"""

from collections.abc import Sequence
from typing import Any

import chess
from sqlalchemy import func, select

from darwin.ledger import commentary, game_review
from darwin.ledger import models as m
from darwin.ledger.lichess import performance
from darwin.ledger.store import Ledger

RESULTS = ("win", "draw", "loss")
PLAYED = (m.LichessGame.finished_at.is_not(None), m.LichessGame.result.in_(RESULTS))


def _base(row: m.LichessGame, site: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "lichess_id": row.lichess_id,
        "url": f"{site.rstrip('/')}/{row.lichess_id}",
        "opponent": row.opponent,
        "opponent_rating": row.opponent_rating,
        "opponent_title": row.opponent_title,
        "color": row.color,
        "result": row.result,
        "status": row.status,
        "rated": row.rated,
        "generation_id": row.generation_id,
        "time_control": row.time_control,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _list_item(row: m.LichessGame, site: str, text: m.Commentary | None) -> dict[str, Any]:
    moves = row.moves.split()
    evals = row.evals if game_review.usable(moves, row.evals) else None
    ours = None
    if evals is not None:
        ours = game_review.review(len(moves), evals, row.color).sides["us"]
    return {
        **_base(row, site),
        "plies": len(moves),
        "curve": None if evals is None else game_review.curve(evals),
        "ours": ours,
        "commentary": commentary.view(text),
    }


async def games_page(
    ledger: Ledger,
    site: str,
    *,
    limit: int,
    before_id: int | None,
    generation: int | None,
    result: str | None,
    rated_only: bool,
) -> dict[str, Any]:
    """Finished games, newest first, `limit` at a time below `before_id`, filtered by
    generation, result and rated. `counts` are per result under the same generation and
    rated filters, so every result's tab shows its number; `generations` and `performance`
    cover every game."""
    async with ledger.session() as s:
        scope = []
        if generation is not None:
            scope.append(m.LichessGame.generation_id == generation)
        if rated_only:
            scope.append(m.LichessGame.rated.is_(True))
        counts = {r: 0 for r in RESULTS}
        for found, n in await s.execute(
            select(m.LichessGame.result, func.count())
            .where(*PLAYED, *scope)
            .group_by(m.LichessGame.result)
        ):
            counts[str(found)] = int(n)
        generations = [
            {"id": int(gen), "games": int(n)}
            for gen, n in await s.execute(
                select(m.LichessGame.generation_id, func.count())
                .where(*PLAYED)
                .group_by(m.LichessGame.generation_id)
                .order_by(m.LichessGame.generation_id.desc())
            )
        ]
        # Only the columns the performance needs: the whole rows carry moves and evaluations.
        played = (
            await s.execute(
                select(
                    m.LichessGame.generation_id,
                    m.LichessGame.rated,
                    m.LichessGame.result,
                    m.LichessGame.opponent_rating,
                ).where(m.LichessGame.finished_at.is_not(None))
            )
        ).all()
        query = select(m.LichessGame).where(*PLAYED, *scope)
        if result is not None:
            query = query.where(m.LichessGame.result == result)
        if before_id is not None:
            query = query.where(m.LichessGame.id < before_id)
        rows = (await s.scalars(query.order_by(m.LichessGame.id.desc()).limit(limit + 1))).all()
        more = len(rows) > limit
        rows = rows[:limit]
        texts = await commentary.of(s, commentary.LICHESS_GAME, [r.id for r in rows])
    return {
        "items": [_list_item(r, site, texts.get(r.id)) for r in rows],
        "next_before_id": rows[-1].id if more and rows else None,
        "counts": {**counts, "total": sum(counts.values())},
        "generations": generations,
        "performance": performance(played),
    }


def _positions(moves: Sequence[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """The FEN after every move and its SAN, start included, up to the first move that is not
    legal from the standard start (none, for a game Lichess accepted)."""
    board = chess.Board()
    fens, sans = [board.fen()], []
    for uci in moves:
        try:
            move = chess.Move.from_uci(uci)
        except chess.InvalidMoveError:
            break
        if move not in board.legal_moves:
            break
        sans.append(board.san(move))
        board.push(move)
        fens.append(board.fen())
    return [{"fen": fen} for fen in fens], sans


async def game_detail(ledger: Ledger, site: str, lichess_id: str) -> dict[str, Any] | None:
    """One finished game move by move: every position with its evaluation and the bot's
    winning chances, every move with its judgement, each side's totals, the move where the
    game turned and the games on either side. None when there is no such game."""
    async with ledger.session() as s:
        row = await s.scalar(
            select(m.LichessGame).where(*PLAYED, m.LichessGame.lichess_id == lichess_id)
        )
        if row is None:
            return None
        neighbour = select(m.LichessGame.lichess_id).where(*PLAYED).limit(1)
        older = await s.scalar(
            neighbour.where(m.LichessGame.id < row.id).order_by(m.LichessGame.id.desc())
        )
        newer = await s.scalar(
            neighbour.where(m.LichessGame.id > row.id).order_by(m.LichessGame.id)
        )
        text = (await commentary.of(s, commentary.LICHESS_GAME, [row.id])).get(row.id)
    moves = row.moves.split()
    positions, sans = _positions(moves)
    played = moves[: len(sans)]
    evals = row.evals if game_review.usable(moves, row.evals) else None
    review = None if evals is None else game_review.review(len(played), evals, row.color)
    if evals is not None:
        for position, cp in zip(positions, evals, strict=False):
            position["eval_cp"] = cp
            position["chances"] = round(100 * game_review.chances(cp))
    return {
        **_base(row, site),
        "rating_after": row.rating_after,
        "commentary": commentary.view(text),
        "analysed": review is not None,
        "positions": positions,
        "moves": [
            {
                "uci": uci,
                "san": san,
                "ours": (ply % 2 == 0) == (row.color == "white"),
                "judgement": None if review is None else review.judgements[ply],
            }
            for ply, (uci, san) in enumerate(zip(played, sans, strict=True))
        ],
        "sides": None if review is None else review.sides,
        "turning_point": None if review is None else review.turning_point,
        "older": older,
        "newer": newer,
    }
