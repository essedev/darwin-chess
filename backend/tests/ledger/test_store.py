from datetime import UTC, datetime, timedelta

import pytest

from darwin.ledger import queries
from darwin.ledger.store import Ledger
from darwin.referee.judge import Phase, Verdict
from darwin.referee.match import MatchResult
from darwin.referee.models import GameRecord, Gate, GateResult, Termination
from darwin.referee.sprt import SprtVerdict

SEED = "0" * 40
CANDIDATE = "a" * 40


def gate(name: Gate, passed: bool = True) -> GateResult:
    return GateResult(name, passed, {"x": 1}, 5)


def won_match() -> MatchResult:
    games = [
        GameRecord("candidate", "random", "1-0", Termination.CHECKMATE, "fen1", "pgn"),
        GameRecord("random", "candidate", "1/2-1/2", Termination.STALEMATE, "fen1", "pgn"),
    ]
    return MatchResult(games, [0, 0, 0, 1, 0], 191.0, 80.0, 3.1, SprtVerdict.H1, "random", "2+0")


async def start(ledger: Ledger, phase: Phase) -> int:
    state = await ledger.state()
    return await ledger.start_experiment(kind="iteration", phase=phase,
                                         base_commit=state.base_commit,
                                         base_generation_id=state.champion.id,
                                         trigger="test")  # fmt: skip


async def test_unseeded_ledger_has_no_state(ledger: Ledger) -> None:
    with pytest.raises(LookupError):
        await ledger.state()


async def test_seed_is_idempotent_and_starts_genesis(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    await ledger.seed("b" * 40)
    state = await ledger.state()
    assert state.phase is Phase.GENESIS
    assert state.champion.commit_sha == SEED
    assert state.base_commit == SEED


async def test_rejection_records_the_failed_gate(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    experiment = await start(ledger, Phase.GENESIS)
    await ledger.set_submission(experiment, "movegen", CANDIDATE, {"files": 1})
    verdict = Verdict(False, [gate(Gate.BUILD), gate(Gate.PERFT, False)], None, None)
    assert await ledger.record_verdict(experiment, verdict) is None
    [row] = await ledger.recent_experiments(5)
    assert (row.status, row.rejected_at_gate) == ("rejected", "perft")
    assert [g.gate for g in await ledger.gates_of(experiment)] == ["build", "perft"]
    assert (await ledger.state()).base_commit == SEED


async def test_phases_advance_with_accepted_candidates(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    genesis = await start(ledger, Phase.GENESIS)
    await ledger.set_submission(genesis, "movegen", CANDIDATE, {})
    await ledger.record_verdict(genesis, Verdict(True, [gate(Gate.PERFT)], None, None))
    state = await ledger.state()
    assert (state.phase, state.base_commit, state.champion.id) == (
        Phase.FIRST_STEPS, CANDIDATE, 0)  # fmt: skip

    first = await start(ledger, Phase.FIRST_STEPS)
    await ledger.set_submission(first, "search", "c" * 40, {})
    promoted = await ledger.record_verdict(first, Verdict(True, [gate(Gate.MATCH)], None,
                                                          won_match()))  # fmt: skip
    assert promoted is not None and promoted.id == 1
    state = await ledger.state()
    assert (state.phase, state.champion.commit_sha) == (Phase.EVOLUTION, "c" * 40)


async def test_spend_sums_by_time_window(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    experiment = await start(ledger, Phase.GENESIS)
    for cost in (0.01, 0.02):
        await ledger.add_llm_call(experiment, "m", input_tokens=10, cached_tokens=0,
                                  output_tokens=5, cost_usd=cost)  # fmt: skip
    now = datetime.now(UTC)
    assert await ledger.spend_since(now - timedelta(hours=1)) == pytest.approx(0.03)
    assert await ledger.spend_since(now + timedelta(seconds=5)) == 0
    assert await ledger.spend_of(experiment) == pytest.approx(0.03)


async def test_experiments_are_searchable_by_hypothesis_and_lesson(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    experiment = await start(ledger, Phase.GENESIS)
    await ledger.set_submission(experiment, "Try magic bitboards", CANDIDATE, {})
    await ledger.set_lesson(experiment, "Slower than mailbox at depth 3")
    assert len(await ledger.search_experiments("bitboard", 5)) == 1
    assert len(await ledger.search_experiments("mailbox", 5)) == 1
    assert await ledger.search_experiments("nnue", 5) == []


async def test_timestamps_come_back_aware(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    [gen0] = await ledger.generations()
    assert gen0.created_at.tzinfo is UTC


async def test_a_rating_of_either_kind_marks_a_champion_as_measured(ledger: Ledger) -> None:
    await ledger.seed(SEED)
    assert not await ledger.has_rating(0)
    await ledger.add_rating(0, "anchors_below", 1320.0, None, {"below_scale": True})
    assert await ledger.has_rating(0)


async def test_match_progress_is_kept_on_the_experiment(ledger: Ledger) -> None:
    await ledger.seed("a" * 40)
    exp = await ledger.start_experiment(
        kind="iteration", phase=Phase.EVOLUTION, base_commit="a" * 40,
        base_generation_id=0, trigger="start",
    )  # fmt: skip
    progress = {"games": 24, "wins": 9, "draws": 8, "losses": 7, "llr": 0.4, "bounds": [-2.9, 2.9]}
    await ledger.set_progress(exp, progress)
    view = await queries.experiment_view(ledger, await ledger.experiment(exp))
    assert (view["progress"], view["title"]) == (progress, None)
