import random
from typing import Any

import chess
import pytest

from darwin.lichess import rules

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


@pytest.mark.parametrize(
    ("clock", "speed"),
    [((15, 0), "ultraBullet"), ((60, 1), "bullet"), ((180, 2), "blitz"), ((600, 0), "rapid"),
     ((1800, 0), "classical")],
)  # fmt: skip
def test_speed_follows_the_lichess_estimate(clock: tuple[int, int], speed: str) -> None:
    assert rules.speed_of(*clock) == speed


@pytest.mark.parametrize(
    ("fen", "plies", "color", "expected"),
    [
        (rules.STARTPOS, 0, "white", True),
        (rules.STARTPOS, 0, "black", False),
        (rules.STARTPOS, 3, "black", True),
        (AFTER_E4, 0, "black", True),  # a position with black to move flips the parity
        (AFTER_E4, 1, "white", True),
    ],
)
def test_our_turn(fen: str, plies: int, color: str, expected: bool) -> None:
    assert rules.our_turn(fen, plies, color) is expected


@pytest.mark.parametrize(
    ("status", "winner", "color", "result"),
    [
        ("started", None, "white", None),
        ("mate", "white", "white", "win"),
        ("resign", "white", "black", "loss"),
        ("outoftime", "black", "black", "win"),
        ("timeout", "white", "black", "loss"),
        ("stalemate", None, "white", "draw"),
        ("draw", None, "black", "draw"),
        ("outoftime", None, "white", "draw"),  # flag against insufficient material
        ("aborted", None, "white", "aborted"),
        ("noStart", "black", "white", "aborted"),  # no move made: not a loss of ours
    ],
)
def test_result_from_our_side(status: str, winner: str | None, color: str, result: str) -> None:
    assert rules.result_for(status, winner, color) == result


def test_position_and_go_commands() -> None:
    assert rules.position_command(rules.STARTPOS, []) == "position startpos"
    assert rules.position_command(rules.STARTPOS, ["e2e4"]) == "position startpos moves e2e4"
    assert rules.position_command(AFTER_E4, ["e7e5"]) == f"position fen {AFTER_E4} moves e7e5"
    go = rules.go_command(wtime=60000, btime=50, winc=2000, binc=2000, color="white",
                          overhead_ms=300)  # fmt: skip
    assert go == "go wtime 59700 btime 50 winc 2000 binc 2000"  # only our clock loses it
    low = rules.go_command(wtime=200, btime=200, winc=0, binc=0, color="black", overhead_ms=300)
    assert low == "go wtime 200 btime 100 winc 0 binc 0"


def test_only_legal_moves_pass() -> None:
    board = rules.board_for(rules.STARTPOS, ["e2e4"])
    assert board.turn == chess.BLACK
    assert rules.is_legal(board, "e7e5")
    assert not rules.is_legal(board, "e2e4")
    assert not rules.is_legal(board, "(none)")
    assert not rules.is_legal(board, "")


def challenge(variant: str = "standard", kind: str = "clock", limit: int = 180) -> dict[str, Any]:
    return {"id": "c1", "variant": {"key": variant},
            "timeControl": {"type": kind, "limit": limit, "increment": 2}}  # fmt: skip


@pytest.mark.parametrize(
    ("offer", "busy", "reason"),
    [
        (challenge(), False, None),
        (challenge(limit=60), False, None),
        (challenge(limit=600), False, None),
        (challenge(), True, "later"),
        (challenge(variant="chess960"), False, "variant"),
        (challenge(variant="fromPosition"), True, "variant"),
        (challenge(limit=30), False, "timeControl"),
        (challenge(limit=900), False, "timeControl"),
        (challenge(kind="correspondence"), False, "timeControl"),
        ({"id": "c2", "variant": {"key": "standard"}, "timeControl": {"type": "unlimited"}},
         False, "timeControl"),
    ],
)  # fmt: skip
def test_which_challenges_we_take(offer: dict[str, Any], busy: bool, reason: str | None) -> None:
    assert rules.decline_reason(offer, busy=busy) == reason


def bot(name: str, rating: int | None, **extra: Any) -> dict[str, Any]:
    perfs = {} if rating is None else {"blitz": {"rating": rating}}
    return {"id": name.lower(), "username": name, "perfs": perfs, **extra}


def pick(bots: list[dict[str, Any]], seed: int = 0) -> str | None:
    return rules.pick_opponent(
        bots, me="darwinbot", my_rating=1500, speed="blitz", rng=random.Random(seed)
    )


def test_opponent_within_the_rating_window() -> None:
    bots = [bot("DarwinBot", 1500), bot("Near", 1750), bot("Far", 2200), bot("Unrated", None)]
    assert {pick(bots, seed) for seed in range(20)} == {"Near"}


def test_opponent_window_widens_when_nobody_is_close() -> None:
    assert pick([bot("Wide", 1050), bot("Far", 2200)]) == "Wide"
    # Nobody even in the wide window: the closest few rather than no game at all.
    assert pick([bot("Far", 2200), bot("DarwinBot", 1500)]) == "Far"


def test_opponent_never_a_flagged_account() -> None:
    assert pick([bot("Cheat", 1500, tosViolation=True), bot("Gone", 1500, disabled=True)]) is None


def test_opponent_is_random_among_the_close_ones() -> None:
    bots = [bot("A", 1400), bot("B", 1600), bot("C", 1500)]
    assert {pick(bots, seed) for seed in range(50)} == {"A", "B", "C"}


def test_rating_of_reads_the_perf() -> None:
    assert rules.rating_of({"perfs": {"blitz": {"rating": 1612, "prov": True}}}, "blitz") == 1612
    assert rules.rating_of({"perfs": {}}, "blitz") is None
    assert rules.rating_of({}, "blitz") is None


def test_a_provisional_rating_aims_at_the_start_rating() -> None:
    fresh = {"perfs": {"blitz": {"rating": 3000, "games": 0, "prov": True}}}
    settled = {"perfs": {"blitz": {"rating": 1640, "games": 40}}}
    assert rules.matchmaking_rating(fresh, "blitz", 1200) == 1200
    assert rules.matchmaking_rating(settled, "blitz", 1200) == 1640
    assert rules.matchmaking_rating({}, "blitz", 1200) == 1200


def test_a_bot_below_everyone_still_finds_the_closest_opponents() -> None:
    bots = [
        bot(name, rating)
        for name, rating in [
            ("A", 2200),
            ("B", 2300),
            ("C", 2400),
            ("D", 2500),
            ("E", 2600),
            ("F", 2900),
        ]
    ]
    picked = {
        rules.pick_opponent(bots, me="x", my_rating=900, speed="blitz", rng=random.Random(seed))
        for seed in range(40)
    }
    assert picked == {"A", "B", "C", "D", "E"}
