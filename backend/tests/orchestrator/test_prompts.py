from dataclasses import replace
from datetime import UTC, datetime

from darwin.ledger import models as m
from darwin.orchestrator.prompts import SessionContext, session_prompt
from darwin.referee.judge import Phase

NOW = datetime(2026, 11, 25, tzinfo=UTC)


def context(kind: str = "iteration", new_lichess_losses: int = 0) -> SessionContext:
    last = m.Experiment(
        id=7,
        phase="evolution",
        status="rejected",
        rejected_at_gate="smoke",
        hypothesis="Faster move ordering",
        base_commit="b" * 40,
        trigger="t",
    )
    gate = m.GateResult(
        gate="smoke",
        passed=False,
        detail={"problem": "illegal_move", "pgn": '[White "candidate"] 1. e4'},
        duration_ms=10,
        experiment_id=7,
    )
    return SessionContext(
        kind=kind,
        trigger="verdict:7",
        phase=Phase.EVOLUTION,
        champion=m.Generation(id=3, commit_sha="c" * 40),
        base_commit="c" * 40,
        recent=[last],
        gates_of_last=[gate],
        jobs=[],
        notes="n" * 10000,
        strategy="- keep it simple",
        max_tool_calls=80,
        new_lichess_losses=new_lichess_losses,
    )


def test_the_last_verdict_comes_with_its_failing_game_and_a_lesson_request() -> None:
    text = session_prompt(context())
    assert "gen-3" in text and "#7: rejected" in text
    assert "illegal_move" in text and "1. e4" in text
    assert "lesson_for_previous" in text
    assert "Run one experiment and submit it" in text


def test_notes_are_cut_to_their_tail() -> None:
    assert session_prompt(context()).count("n") < 5000


def test_a_reflection_forbids_submitting() -> None:
    text = session_prompt(context("reflection"))
    assert "do not submit" in text and "STRATEGY.md" in text


def test_new_lichess_losses_are_announced_only_when_there_are_some() -> None:
    assert "Lichess" not in session_prompt(context())
    assert "1 new loss since" in session_prompt(context(new_lichess_losses=1))
    assert "3 new losses since your last session" in session_prompt(context(new_lichess_losses=3))


def test_the_session_prompt_states_every_limit_and_the_start_time() -> None:
    ctx = replace(context(), started_at=datetime(2026, 11, 25, 22, 51, tzinfo=UTC))
    text = session_prompt(ctx)
    assert "started at 22:51 UTC" in text
    assert "40 minutes, 80 tool calls, 0.25 $" in text
