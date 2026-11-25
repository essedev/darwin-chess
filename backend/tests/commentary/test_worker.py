"""The worker on a real ledger, with a fake model: no network, no spend."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from darwin.commentary import prompts
from darwin.commentary.model import Written
from darwin.commentary.worker import CommentaryWorker, budget_allows
from darwin.config import Settings
from darwin.ledger import commentary as records
from darwin.ledger import lichess
from darwin.ledger import models as m
from darwin.ledger.commentary import Subject
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase, Verdict
from darwin.referee.match import MatchResult
from darwin.referee.models import GameRecord, Gate, GateResult, Termination
from darwin.referee.sprt import SprtVerdict

MOVES = "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3 f8c5 c2c3 d7d6 b1d2 a7a6"


class FakeWriter:
    """Records every call; answers each required field, or nothing (a refusal)."""

    def __init__(self, *, refuse: bool = False, cost: float = 0.001) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.refuse = refuse
        self.cost = cost

    async def write(self, system: str, prompt: str, schema: dict[str, Any]) -> Written | None:
        self.calls.append((system, prompt, schema))
        if self.refuse:
            return None
        fields = {name: f"{name} text {len(self.calls)}" for name in schema["required"]}
        return Written(fields, "claude-haiku-5-5", 301, 51, self.cost)


async def no_evaluation(settings: Settings, moves: list[str], color: str) -> list[int]:
    raise AssertionError("evaluations were already stored")


def make(ledger: Ledger, writer: FakeWriter | None, **settings: Any) -> CommentaryWorker:
    return CommentaryWorker(Settings(**settings), ledger, writer, evaluate=no_evaluation)


async def game(
    ledger: Ledger, lichess_id: str, *, result: str = "loss", moves: str = MOVES,
    evals: list[int] | None = None,
) -> int:  # fmt: skip
    await lichess.start_game(
        ledger, lichess_id=lichess_id, generation_id=0, color="white", opponent="maia1",
        opponent_rating=1500, opponent_title="BOT", rated=True, time_control="180+2",
    )  # fmt: skip
    game_id = await lichess.finish_game(
        ledger, lichess_id, status="resign", result=result, moves=moves, rating_after=1490
    )
    if evals is not None:
        await lichess.set_evals(ledger, game_id, evals)
    return game_id


async def judged(ledger: Ledger, hypothesis: str, *, match: bool) -> int:
    exp = await ledger.start_experiment(
        kind="iteration", phase=Phase.FIRST_STEPS, base_commit="0" * 40,
        base_generation_id=0, trigger="start",
    )  # fmt: skip
    await ledger.set_submission(exp, hypothesis, f"{exp:040d}", {"files": 1})
    result = None
    if match:
        games = [
            GameRecord("candidate", "random", "1-0", Termination.CHECKMATE, "fen-a", ""),
            GameRecord("random", "candidate", "0-1", Termination.CHECKMATE, "fen-a", ""),
        ]
        result = MatchResult(games, [0, 0, 0, 0, 1], 400.0, 100.0, 3.0, SprtVerdict.H1,
                             "random", "1+0.01")  # fmt: skip
    gates = [GateResult(Gate.MATCH, match, {}, 1)]
    await ledger.record_verdict(exp, Verdict(match, gates, None, result))
    return exp


async def stored(ledger: Ledger) -> list[m.Commentary]:
    async with ledger.session() as s:
        return list((await s.scalars(select(m.Commentary).order_by(m.Commentary.id))).all())


def test_the_budget_keeps_room_for_one_more_call() -> None:
    assert budget_allows(0.0, 0.20)
    assert budget_allows(0.198, 0.20)
    assert not budget_allows(0.1981, 0.20)
    assert not budget_allows(0.0, 0.0)


async def test_off_without_the_anthropic_provider_or_a_key(ledger: Ledger) -> None:
    for settings in (
        Settings(llm_provider="openrouter", llm_api_key="k"),
        Settings(llm_provider="anthropic", llm_api_key=""),
        Settings(llm_provider="fake", llm_model="scripted", llm_api_key="k"),
    ):
        off = CommentaryWorker.from_settings(settings, ledger)
        assert not off.enabled
        off.enqueue(records.MATCH, 1)
        assert off.queue.empty()
        await off.run()  # returns at once
    on = CommentaryWorker.from_settings(Settings(llm_provider="anthropic", llm_api_key="k"), ledger)
    assert on.enabled  # nothing is called until it runs
    await on.close()


async def test_a_lichess_game_is_commented_from_its_evaluations(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    game_id = await game(ledger, "AbCd1234", evals=[20] * 10 + [-500, -500, -10000])
    writer = FakeWriter()
    worker = make(ledger, writer)
    worker.enqueue(records.LICHESS_GAME, game_id)
    worker.enqueue(records.LICHESS_GAME, game_id)  # queued once
    await worker.work(until_idle=True)

    (call,) = writer.calls
    assert "6. Nbd2 (-5.0) a6 (M-)" in call[1]
    assert call[2]["required"] == ["it", "en"]
    (row,) = await stored(ledger)
    assert (row.kind, row.subject_id, row.text_it, row.text_en) == (
        "lichess_game", game_id, "it text 1", "en text 1",
    )  # fmt: skip
    assert (row.input_tokens, row.output_tokens, row.cost_usd) == (301, 51, 0.001)

    assert not await worker.comment(Subject(records.LICHESS_GAME, game_id))  # done already
    assert len(writer.calls) == 1


async def test_a_game_without_evaluations_is_evaluated_first(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    game_id = await game(ledger, "AbCd1234", result="win")
    seen: list[tuple[list[str], str]] = []

    async def evaluate(settings: Settings, moves: list[str], color: str) -> list[int]:
        seen.append((moves, color))
        return [30] * (len(moves) + 1)

    writer = FakeWriter()
    worker = CommentaryWorker(Settings(), ledger, writer, evaluate=evaluate)
    assert await worker.comment(Subject(records.LICHESS_GAME, game_id))
    assert seen == [(MOVES.split(), "white")]
    row = await records.lichess_game(ledger, game_id)
    assert row is not None and row.evals == [30] * 13


async def test_short_or_aborted_games_get_nothing(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    short = await game(ledger, "short001", moves="e2e4 e7e5")
    aborted = await game(ledger, "abort001", result="aborted")
    writer = FakeWriter()
    worker = make(ledger, writer)
    for game_id in (short, aborted, 999):
        assert not await worker.comment(Subject(records.LICHESS_GAME, game_id))
    assert writer.calls == [] and await stored(ledger) == []


async def test_a_match_is_commented_from_its_facts(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    exp = await judged(ledger, "Play captures first", match=True)
    writer = FakeWriter()
    worker = make(ledger, writer)
    await worker.after_verdict(exp)
    await worker.work(until_idle=True)

    match_call, translation = writer.calls
    assert "in its own words: Play captures first" in match_call[1]
    assert "picks random legal moves" in match_call[1]
    assert "2 wins, 0 draws, 0 losses in 2 games" in match_call[1]
    assert "checkmate 2 (new version won 2)" in match_call[1]
    assert "accepted: the new version becomes the champion" in match_call[1]
    assert translation[2]["required"] == ["hypothesis"]
    kinds = [(r.kind, r.text_en) for r in await stored(ledger)]
    assert kinds == [("match", "en text 1"), ("hypothesis", "Play captures first")]


async def test_hypothesis_and_lesson_share_one_call_and_keep_the_original(
    ledger: Ledger,
) -> None:
    await ledger.seed("0" * 40)
    exp = await judged(ledger, "Order moves by MVV-LVA", match=False)
    await ledger.set_lesson(exp, "Perft first, then speed.")
    writer = FakeWriter(cost=0.001)
    worker = make(ledger, writer)
    worker.enqueue(records.HYPOTHESIS, exp)
    worker.enqueue(records.LESSON, exp)
    await worker.work(until_idle=True)

    (call,) = writer.calls
    assert call[2]["required"] == ["hypothesis", "lesson"]
    assert "Perft first, then speed." in call[1]
    rows = await stored(ledger)
    assert [(r.kind, r.subject_id, r.text_it, r.text_en) for r in rows] == [
        ("hypothesis", exp, "hypothesis text 1", "Order moves by MVV-LVA"),
        ("lesson", exp, "lesson text 1", "Perft first, then speed."),
    ]
    assert [r.input_tokens for r in rows] == [151, 150]
    assert sum(r.cost_usd for r in rows) == pytest.approx(0.001)


async def test_a_title_is_written_in_both_languages_from_the_hypothesis(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    exp = await judged(ledger, "Add a doubled-pawn penalty to the go mover's eval", match=False)
    writer = FakeWriter()
    worker = make(ledger, writer)
    worker.after_submit(exp)
    await worker.work(until_idle=True)

    title_call, translation_call = writer.calls
    assert title_call[0] == prompts.TITLE_SYSTEM
    assert "doubled-pawn penalty" in title_call[1]
    assert title_call[2]["required"] == ["it", "en"]
    assert translation_call[2]["required"] == ["hypothesis"]
    rows = await stored(ledger)
    assert [(r.kind, r.text_it, r.text_en) for r in rows] == [
        ("title", "it text 1", "en text 1"),
        ("hypothesis", "hypothesis text 2", "Add a doubled-pawn penalty to the go mover's eval"),
    ]
    worker.enqueue(records.TITLE, exp)  # already written: nothing to do
    await worker.work(until_idle=True)
    assert len(writer.calls) == 2


async def test_a_refusal_stores_nothing_and_the_worker_goes_on(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    exp = await judged(ledger, "Try a deeper search", match=False)
    writer = FakeWriter(refuse=True)
    worker = make(ledger, writer)
    worker.enqueue(records.HYPOTHESIS, exp)
    worker.enqueue(records.HYPOTHESIS, 999)  # no such experiment: skipped
    await worker.work(until_idle=True)
    assert len(writer.calls) == 1 and await stored(ledger) == []


async def test_a_spent_budget_calls_nothing_and_drops_the_queue(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    first = await judged(ledger, "Try a deeper search", match=False)
    second = await judged(ledger, "Try a shallower search", match=False)
    writer = FakeWriter(cost=0.1)
    worker = make(ledger, writer, commentary_daily_usd=0.101)
    worker.enqueue(records.HYPOTHESIS, first)
    worker.enqueue(records.HYPOTHESIS, second)
    await worker.work(until_idle=True)
    assert len(writer.calls) == 1  # the second would pass the daily ceiling
    assert worker.queue.empty() and not worker.pending
    assert [r.subject_id for r in await stored(ledger)] == [first]


async def test_backfill_queues_what_is_missing_oldest_first(
    ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ledger.seed("0" * 40)
    early = await judged(ledger, "First idea", match=True)
    await ledger.set_lesson(early, "It worked.")
    later = await judged(ledger, "Second idea", match=False)
    played = await game(ledger, "AbCd1234", evals=[0] * 13)
    await game(ledger, "short001", moves="e2e4")
    async with ledger.session() as s:  # the game finished long ago
        row = await s.get_one(m.LichessGame, played)
        row.finished_at = datetime.now(UTC) - timedelta(days=1)
    match_id = (await records.match_ids_of(ledger, early))[0]
    await records.add(
        ledger, Subject(records.HYPOTHESIS, early), text_it="Prima idea", text_en="First idea",
        model="x", input_tokens=1, output_tokens=1, cost_usd=0.0,
    )  # fmt: skip

    assert await records.missing(ledger) == [
        Subject(records.LICHESS_GAME, played),
        Subject(records.TITLE, early),  # dated at the submission, before the verdict
        Subject(records.MATCH, match_id),
        Subject(records.HYPOTHESIS, later),
        Subject(records.LESSON, early),  # written by the session of `later`
        Subject(records.TITLE, later),
    ]
    worker = make(ledger, FakeWriter())
    assert await worker.backfill() == 6
    assert await worker.backfill() == 6  # already pending: not queued twice
    assert worker.queue.qsize() == 6


async def test_the_worker_task_backfills_and_comments(
    ledger: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ledger.seed("0" * 40)
    exp = await judged(ledger, "First idea", match=False)
    await judged(ledger, "Second idea", match=False)
    writer = FakeWriter(cost=1.0)  # the first call spends the whole day
    worker = make(ledger, writer)

    async def stop() -> None:
        raise RuntimeError("stopped where it would sleep until tomorrow")

    monkeypatch.setattr(worker, "_until_tomorrow", stop)
    with pytest.raises(RuntimeError, match="tomorrow"):
        await worker.run()
    assert [r.subject_id for r in await stored(ledger)] == [exp]
