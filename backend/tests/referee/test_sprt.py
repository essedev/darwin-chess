import math

import pytest

from darwin.referee.match import progress
from darwin.referee.models import GameRecord, Termination
from darwin.referee.sprt import (
    SprtParams,
    SprtVerdict,
    decide,
    elo_estimate,
    expected_score,
    llr,
    pentanomial,
)

PARAMS = SprtParams(0, 10)


def test_bounds_for_five_percent_errors() -> None:
    lower, upper = PARAMS.bounds()
    assert lower == pytest.approx(-2.944, abs=1e-3)
    assert upper == pytest.approx(2.944, abs=1e-3)


def test_pentanomial_counts_pair_scores() -> None:
    assert pentanomial([0, 0.5, 1, 1, 1.5, 2, 2, 2]) == [1, 1, 2, 1, 3]


def test_llr_sign_follows_results() -> None:
    assert llr([0, 5, 40, 25, 10], PARAMS) > 0
    assert llr([10, 25, 40, 5, 0], PARAMS) < 0
    assert llr([0, 0, 0, 0, 0], PARAMS) == 0


def test_llr_grows_with_evidence() -> None:
    small = llr([1, 4, 10, 6, 3], PARAMS)
    assert llr([10, 40, 100, 60, 30], PARAMS) == pytest.approx(10 * small)


def test_clear_superiority_crosses_upper_bound() -> None:
    value = llr([0, 0, 2, 10, 30], SprtParams(0, 150))
    assert decide(value, SprtParams(0, 150)) is SprtVerdict.H1


def test_equal_engines_drift_to_h0() -> None:
    value = llr([100, 400, 1000, 400, 100], PARAMS)
    assert decide(value, PARAMS) is SprtVerdict.H0


def test_elo_estimate_is_zero_for_even_score() -> None:
    elo, error = elo_estimate([10, 20, 40, 20, 10])
    assert elo == pytest.approx(0, abs=1e-9)
    assert 0 < error < 200


def test_elo_estimate_matches_logistic_score() -> None:
    elo, _ = elo_estimate([0, 0, 0, 100, 0])  # every pair scores 1.5 of 2: 75%
    assert expected_score(elo) == pytest.approx(0.75, abs=1e-3)
    assert math.isfinite(elo)


def test_progress_counts_the_candidate_results_and_carries_the_bounds() -> None:
    games = [
        GameRecord("candidate", "champion", "1-0", Termination.CHECKMATE, "a", ""),
        GameRecord("champion", "candidate", "1-0", Termination.CHECKMATE, "a", ""),
        GameRecord("candidate", "champion", "1/2-1/2", Termination.ADJUDICATION, "b", ""),
        GameRecord("champion", "candidate", "0-1", Termination.CHECKMATE, "b", ""),
    ]
    params = SprtParams(0, 10)
    assert progress(games, "candidate", 0.81234, params) == {
        "games": 4,
        "wins": 2,
        "draws": 1,
        "losses": 1,
        "llr": 0.812,
        "bounds": [round(params.bounds()[0], 3), round(params.bounds()[1], 3)],
    }
