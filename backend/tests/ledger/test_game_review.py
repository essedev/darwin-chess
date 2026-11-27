"""Judging the moves of a Lichess game from Stockfish's evaluations."""

import pytest

from darwin.ledger import game_review as gr


def test_chances_are_symmetric_and_capped() -> None:
    assert gr.chances(0) == 0
    assert gr.chances(-250) == pytest.approx(-gr.chances(250))
    assert gr.chances(10000) == gr.chances(gr.CP_CAP)  # a forced mate lands on the cap
    assert 0.9 < gr.chances(gr.CP_CAP) < 1


@pytest.mark.parametrize(
    ("given_away", "expected"),
    [
        (0.0, None),
        (0.099, None),
        (0.1, "inaccuracy"),
        (0.2, "mistake"),
        (0.3, "blunder"),
        (1.5, "blunder"),
    ],
)
def test_judge_uses_the_thresholds_of_lichess(given_away: float, expected: str | None) -> None:
    assert gr.judge(given_away) == expected


def test_the_same_pawns_matter_only_when_the_game_is_open() -> None:
    # White, us: three pawns given away in a won position, then three more from level.
    won = gr.review(1, [1000, 700], "white")
    level = gr.review(1, [0, -300], "white")
    assert won.judgements == [None]
    assert level.judgements == ["blunder"]


def test_review_judges_both_sides_from_the_bot_evaluations() -> None:
    # Black, us: White moves on even plies, and move `ply` goes from evals[ply] to
    # evals[ply + 1]. Our second move (ply 3) throws almost four pawns away.
    evals = [0, -20, -20, -20, -400, -380, -400]
    review = gr.review(6, evals, "black")
    assert review.ours == [False, True, False, True, False, True]
    assert review.judgements == [None, None, None, "blunder", None, None]
    assert review.turning_point == 3
    assert review.sides["us"] == {"blunder": 1, "mistake": 0, "inaccuracy": 0, "acpl": 133}
    # Their moves lose 0, 0 and 20 centipawns from their side (the first one gains 20).
    assert review.sides["them"] == {"blunder": 0, "mistake": 0, "inaccuracy": 0, "acpl": 7}


def test_the_turning_point_is_the_largest_swing_of_either_side() -> None:
    # White, us: our mistake at ply 0, then their blunder at ply 1 hands the game back.
    review = gr.review(2, [0, -170, 500], "white")
    assert review.judgements[0] in gr.JUDGEMENTS
    assert review.judgements[1] == "blunder"
    assert review.turning_point == 1


def test_a_quiet_game_has_no_turning_point() -> None:
    review = gr.review(2, [20, 25, 15], "white")
    assert review.judgements == [None, None]
    assert review.turning_point is None


def test_review_refuses_evaluations_that_do_not_cover_the_moves() -> None:
    with pytest.raises(ValueError):
        gr.review(3, [0, 0, 0], "white")


def test_usable_needs_one_evaluation_per_position() -> None:
    assert gr.usable(["e2e4"], [0, 10])
    assert not gr.usable(["e2e4"], [0])
    assert not gr.usable(["e2e4"], None)


def test_curve_keeps_short_games_and_samples_long_ones() -> None:
    assert gr.curve([0, 1000, -1000]) == [0, 95, -95]
    long = list(range(0, 1001, 10))  # 101 positions
    sampled = gr.curve(long, points=5)
    assert len(sampled) == 5
    assert sampled[0] == 0
    assert sampled[-1] == round(100 * gr.chances(1000))
    assert sampled == sorted(sampled)
