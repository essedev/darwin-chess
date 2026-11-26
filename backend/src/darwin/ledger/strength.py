"""The joint Elo of every generation, read from the ledger and cached in the process.

The evidence:
- every rung of every anchor rating snapshot (`anchors` and `anchors_below`): the games against
  Stockfish at its nominal Elo. Lichess snapshots stay out: another pool, another scale;
- the SPRT match that promoted each generation over its parent champion, the generation just
  before it. gen-1's match was against the random player, which has no Elo, so it stays out;
  so do rejected candidates, which would each add an unknown with a single match and nothing to
  say about the generations;
- but not the matches of the generations older than the first one rated against the anchors
  (gen-1 and gen-2 in production, promoted before the ladder existed). Their only link is a
  dangling chain of near-whitewash matches that adds nothing to the others and would put
  numbers like -97 ± 601 on the chart: they stay "not rated".

A match enters as points out of games (wins plus half the draws): the anchor rungs keep only
their score, and the same model for every series keeps the fit honest. The pentanomial would
only narrow the margins of the head-to-head matches, by about a sixth on today's drawish ones.

The estimate is derived, never recorded: snapshots keep each measure as it was taken. The fit
is recomputed only when the ledger holds a new snapshot or a new generation (whose promoting
match is written in the same transaction).
"""

import asyncio
from weakref import WeakKeyDictionary

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from darwin.ledger import models as m
from darwin.ledger.elo_fit import Anchor, Estimate, Series, fit
from darwin.ledger.store import Ledger
from darwin.referee.engines import RANDOM_PLAYER

ANCHOR_SOURCES = ("anchors", "anchors_below")
LEGACY_RUNG_GAMES = 40  # rungs recorded before the snapshot stored its games: 20 pairs each

Version = tuple[int, int]  # last anchor snapshot, last generation
_cache: WeakKeyDictionary[Ledger, tuple[Version, dict[int, Estimate]]] = WeakKeyDictionary()


async def joint_elo(ledger: Ledger) -> dict[int, Estimate]:
    """The estimate of every generation the anchors can measure, by generation id."""
    async with ledger.session() as s:  # one read transaction: the version matches the evidence
        last_snapshot = await s.scalar(
            select(func.max(m.RatingSnapshot.id)).where(m.RatingSnapshot.source.in_(ANCHOR_SOURCES))
        )
        last_generation = await s.scalar(select(func.max(m.Generation.id)))
        version = (last_snapshot or 0, last_generation or 0)
        cached = _cache.get(ledger)
        if cached is not None and cached[0] == version:
            return cached[1]
        series = await evidence(s)
    estimates = await asyncio.to_thread(fit, series)
    _cache[ledger] = (version, estimates)
    return estimates


async def expected_elo(ledger: Ledger, generation_id: int) -> float | None:
    """Where a new champion should sit before it is rated: its parent's joint Elo plus the
    gain of the match that promoted it. None when the parent has no estimate."""
    async with ledger.session() as s:
        generation = await s.get(m.Generation, generation_id)
    if generation is None or generation.elo_vs_parent is None:
        return None
    parent = (await joint_elo(ledger)).get(generation_id - 1)
    return None if parent is None else parent.elo + generation.elo_vs_parent


async def evidence(s: AsyncSession) -> list[Series]:
    series: list[Series] = []
    snapshots = (
        await s.scalars(select(m.RatingSnapshot).where(m.RatingSnapshot.source.in_(ANCHOR_SOURCES)))
    ).all()
    if not snapshots:
        return series
    first_rated = min(snap.generation_id for snap in snapshots)
    for snap in snapshots:
        for rung in (snap.detail or {}).get("anchors", []):
            games = int(rung.get("games", LEGACY_RUNG_GAMES))
            points = round(float(rung["score"]) * games * 2) / 2  # the score is rounded
            series.append(Series(snap.generation_id, Anchor(float(rung["elo"])), games, points))
    gens = (await s.scalars(select(m.Generation).order_by(m.Generation.id))).all()
    winners = [g.experiment_id for g in gens if g.experiment_id is not None]
    matches = await s.scalars(
        select(m.Match)
        .where(m.Match.experiment_id.in_(winners), m.Match.kind == "sprt")
        .order_by(m.Match.id)
    )
    promoting = {x.experiment_id: x for x in matches}  # ascending: the latest wins
    for parent, gen in zip(gens, gens[1:], strict=False):
        match = promoting.get(gen.experiment_id)
        if match is None or match.engine_b == RANDOM_PLAYER or parent.id < first_rated:
            continue
        games = match.wins + match.draws + match.losses
        series.append(Series(gen.id, parent.id, games, match.wins + match.draws / 2))
    return series
