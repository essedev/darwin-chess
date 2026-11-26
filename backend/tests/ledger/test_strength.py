import pytest

from darwin.ledger import strength
from darwin.ledger.elo_fit import Anchor, Series, fit
from darwin.ledger.store import Ledger
from darwin.referee.judge import Verdict
from darwin.referee.match import MatchResult
from darwin.referee.models import GameRecord, Gate, GateResult, Termination
from darwin.referee.sprt import SprtVerdict


def match(opponent: str, wins: int, draws: int, losses: int, elo: float) -> MatchResult:
    def game(result: str) -> GameRecord:
        return GameRecord("candidate", opponent, result, Termination.CHECKMATE, "fen", "pgn")

    games = [game("1-0")] * wins + [game("1/2-1/2")] * draws + [game("0-1")] * losses
    return MatchResult(games, [0] * 5, elo, 30.0, 3.0, SprtVerdict.H1, opponent, "8+0.08")


async def promote(ledger: Ledger, commit: str, result: MatchResult) -> int:
    state = await ledger.state()
    exp = await ledger.start_experiment(kind="iteration", phase=state.phase,
                                        base_commit=state.base_commit,
                                        base_generation_id=state.champion.id,
                                        trigger="test")  # fmt: skip
    await ledger.set_submission(exp, "h", commit, {"files": 1})
    gate = GateResult(Gate.MATCH, True, {}, 1)
    promoted = await ledger.record_verdict(exp, Verdict(True, [gate], None, result))
    assert promoted is not None
    return promoted.id


def rung(elo: int, score: float, games: int | None = None) -> dict[str, float]:
    found = {"elo": elo, "score": score, "elo_diff": 0.0, "error": 100.0}
    return found if games is None else {**found, "games": games}


async def test_joint_estimate_from_the_ledger(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    await promote(ledger, "1" * 40, match("random", 10, 0, 0, 400))
    await promote(ledger, "2" * 40, match("champion", 20, 0, 4, 300))  # before the anchors
    await promote(ledger, "3" * 40, match("champion", 30, 20, 10, 120))
    await promote(ledger, "4" * 40, match("champion", 25, 30, 15, 50))
    # gen-3 from before snapshots stored their games (40 each), gen-4 with 80 games
    await ledger.add_rating(3, "anchors", 1400.0, 120.0, {"anchors": [rung(1320, 0.613)]})
    await ledger.add_rating(4, "anchors", 1500.0, 90.0, {"anchors": [rung(1600, 0.425, 80)]})
    await ledger.add_rating(4, "lichess", 1700.0, 50.0, {})

    joint = await strength.joint_elo(ledger)

    expected = fit(
        [
            Series(3, Anchor(1320), 40, 24.5),
            Series(4, Anchor(1600), 80, 34),
            Series(4, 3, 70, 25 + 15),
        ]
    )
    assert set(joint) == {3, 4}  # gen-1 met only the random player, gen-2 predates the ladder
    for gen in (3, 4):
        assert joint[gen].elo == pytest.approx(expected[gen].elo)
        assert joint[gen].error == pytest.approx(expected[gen].error)
    assert await strength.expected_elo(ledger, 4) == pytest.approx(joint[3].elo + 50)
    assert await strength.expected_elo(ledger, 3) is None  # gen-2 has no estimate


async def test_the_fit_is_recomputed_only_when_the_evidence_grows(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    await promote(ledger, "1" * 40, match("random", 10, 0, 0, 400))
    await promote(ledger, "2" * 40, match("champion", 30, 20, 10, 120))
    await ledger.add_rating(1, "anchors", 1400.0, 120.0, {"anchors": [rung(1320, 0.6)]})

    first = await strength.joint_elo(ledger)
    assert await strength.joint_elo(ledger) is first
    assert set(first) == {1, 2}

    await ledger.add_rating(2, "anchors", 1500.0, 100.0, {"anchors": [rung(1600, 0.4)]})
    second = await strength.joint_elo(ledger)
    assert second is not first and second[2].error < first[2].error

    await promote(ledger, "3" * 40, match("champion", 30, 20, 10, 120))
    third = await strength.joint_elo(ledger)
    assert set(third) == {1, 2, 3}
