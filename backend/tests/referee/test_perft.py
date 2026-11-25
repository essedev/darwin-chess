import random
from typing import Any

import chess

from darwin.referee.perft import Divide, compare, parse_divide, random_positions, reference_divide

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


def test_reference_matches_known_counts() -> None:
    assert sum(reference_divide(chess.STARTING_FEN, 3).values()) == 8902
    assert sum(reference_divide(KIWIPETE, 2).values()) == 2039


def test_parse_divide_ignores_noise() -> None:
    lines = ["info string hello", "e2e4: 20", "e7e8q: 3", "garbage", "total: 23"]
    assert parse_divide(lines) == Divide({"e2e4": 20, "e7e8q": 3}, 23)


def test_compare_accepts_a_correct_divide() -> None:
    expected = reference_divide(KIWIPETE, 1)
    got = Divide(dict(expected), sum(expected.values()))
    assert compare(KIWIPETE, 1, expected, got) is None


def problem(expected: dict[str, int], got: Divide) -> dict[str, Any]:
    found = compare("f", 2, expected, got)
    assert found is not None
    return found


def test_compare_reports_the_first_problem() -> None:
    expected = {"a2a3": 20, "e2e4": 20}
    assert problem(expected, Divide({"a2a3": 20}, 20))["problem"] == "missing_moves"
    assert problem(expected, Divide({**expected, "e1g1": 1}, 41))["moves"] == ["e1g1"]
    wrong = problem(expected, Divide({"a2a3": 19, "e2e4": 20}, 39))
    assert wrong == {"fen": "f", "depth": 2, "problem": "wrong_count", "move": "a2a3",
                     "expected": 20, "got": 19}  # fmt: skip
    assert problem(expected, Divide(expected, 41))["problem"] == "wrong_total"


def test_random_positions_are_distinct_playable_and_reproducible() -> None:
    fens = random_positions(random.Random(7), 12)
    assert fens == random_positions(random.Random(7), 12)
    assert len(set(fens)) == 12
    assert all(not chess.Board(fen).is_game_over() for fen in fens)
