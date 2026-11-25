"""Ledger writes and reads for the commentary of the public site (`commentaries`).

The agent never reads this table: commentary is for visitors only.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from darwin.ledger import models as m
from darwin.ledger.store import Ledger

LICHESS_GAME = "lichess_game"
MATCH = "match"
HYPOTHESIS = "hypothesis"
LESSON = "lesson"
KINDS = (LICHESS_GAME, MATCH, HYPOTHESIS, LESSON)

# Shorter Lichess games get no commentary: there is too little to say, and Stockfish does
# not evaluate them (the same threshold as the bot's analysis).
MIN_GAME_PLIES = 10
COMMENTED_RESULTS = ("win", "loss", "draw")


@dataclass(frozen=True, order=True)
class Subject:
    """What a commentary is about: a kind and the id of its row."""

    kind: str
    subject_id: int


def game_is_commented(row: m.LichessGame) -> bool:
    return (
        row.finished_at is not None
        and row.result in COMMENTED_RESULTS
        and len(row.moves.split()) >= MIN_GAME_PLIES
    )


async def add(
    ledger: Ledger,
    subject: Subject,
    *,
    text_it: str,
    text_en: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> bool:
    """Stores a commentary; False when the subject already has one (kept as it is)."""
    try:
        async with ledger.session() as s:
            s.add(
                m.Commentary(
                    kind=subject.kind,
                    subject_id=subject.subject_id,
                    text_it=text_it,
                    text_en=text_en,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                )
            )
    except IntegrityError:
        return False
    return True


async def exists(ledger: Ledger, subject: Subject) -> bool:
    async with ledger.session() as s:
        found = await s.scalar(
            select(m.Commentary.id).where(
                m.Commentary.kind == subject.kind, m.Commentary.subject_id == subject.subject_id
            )
        )
    return found is not None


async def spend_since(ledger: Ledger, since: datetime) -> float:
    async with ledger.session() as s:
        total = await s.scalar(
            select(func.coalesce(func.sum(m.Commentary.cost_usd), 0.0)).where(
                m.Commentary.created_at >= since
            )
        )
    return float(total or 0.0)


async def of(s: AsyncSession, kind: str, ids: Iterable[int]) -> dict[int, m.Commentary]:
    """The commentaries of one kind for these subjects, by subject id (inside a session)."""
    wanted = list(set(ids))
    if not wanted:
        return {}
    rows = await s.scalars(
        select(m.Commentary).where(m.Commentary.kind == kind, m.Commentary.subject_id.in_(wanted))
    )
    return {row.subject_id: row for row in rows}


def view(row: m.Commentary | None) -> dict[str, str] | None:
    """The API shape of a commentary."""
    return None if row is None else {"it": row.text_it, "en": row.text_en}


def italian(row: m.Commentary | None) -> str | None:
    return None if row is None else row.text_it


async def missing(ledger: Ledger) -> list[Subject]:
    """Everything that should have a commentary and has none, oldest first."""
    async with ledger.session() as s:
        done: dict[str, set[int]] = {kind: set() for kind in KINDS}
        for kind, subject_id in (
            await s.execute(select(m.Commentary.kind, m.Commentary.subject_id))
        ).all():
            done.setdefault(kind, set()).add(subject_id)
        games = (
            await s.scalars(select(m.LichessGame).where(m.LichessGame.finished_at.is_not(None)))
        ).all()
        matches = (await s.scalars(select(m.Match))).all()
        experiments = (
            await s.scalars(
                select(m.Experiment).where(
                    m.Experiment.hypothesis.is_not(None) | m.Experiment.lesson.is_not(None)
                )
            )
        ).all()
    dated: list[tuple[datetime, Subject]] = []
    for game in games:
        if game_is_commented(game) and game.id not in done[LICHESS_GAME]:
            dated.append((game.finished_at or game.created_at, Subject(LICHESS_GAME, game.id)))
    for match in matches:
        if match.id not in done[MATCH]:
            dated.append((match.finished_at or match.created_at, Subject(MATCH, match.id)))
    # A lesson is written by a later session, the one that submits next: date it there.
    submitted = sorted((e.id, e.created_at) for e in experiments if e.hypothesis)
    for exp in experiments:
        if exp.hypothesis and exp.id not in done[HYPOTHESIS]:
            dated.append((exp.created_at, Subject(HYPOTHESIS, exp.id)))
        if exp.lesson and exp.id not in done[LESSON]:
            writer = next((at for exp_id, at in submitted if exp_id > exp.id), None)
            dated.append((writer or exp.finished_at or exp.created_at, Subject(LESSON, exp.id)))
    dated.sort(key=lambda item: (item[0], KINDS.index(item[1].kind), item[1].subject_id))
    return [subject for _, subject in dated]


async def match_ids_of(ledger: Ledger, experiment_id: int) -> Sequence[int]:
    async with ledger.session() as s:
        query = select(m.Match.id).where(m.Match.experiment_id == experiment_id)
        return (await s.scalars(query.order_by(m.Match.id))).all()


async def match_inputs(
    ledger: Ledger, match_id: int
) -> tuple[m.Match, Sequence[m.Game], m.Experiment | None] | None:
    """A match with its games and the experiment it judged, or None when there is none."""
    async with ledger.session() as s:
        match = await s.get(m.Match, match_id)
        if match is None:
            return None
        games = (
            await s.scalars(select(m.Game).where(m.Game.match_id == match_id).order_by(m.Game.id))
        ).all()
        experiment = await s.get(m.Experiment, match.experiment_id) if match.experiment_id else None
    return match, games, experiment


async def lichess_game(ledger: Ledger, game_id: int) -> m.LichessGame | None:
    async with ledger.session() as s:
        return await s.get(m.LichessGame, game_id)


async def experiment(ledger: Ledger, experiment_id: int) -> m.Experiment | None:
    async with ledger.session() as s:
        return await s.get(m.Experiment, experiment_id)
