"""The gates against real engines in real containers. Slow: a few minutes in total."""

import subprocess

import pytest

from darwin.config import Settings
from darwin.referee import engines
from darwin.referee.gates import MatchPolicy, Policy, match_gate, smoke_gate
from darwin.referee.models import Gate
from darwin.referee.perft import perft_gate
from darwin.referee.sprt import SprtParams

from .conftest import faulty

pytestmark = pytest.mark.docker

FAST = Policy(smoke_pairs=2, smoke_tc="2+0.02")
VS_RANDOM = MatchPolicy(SprtParams(0, 150), "2+0.02", batch_pairs=6, max_pairs=60)


def no_leftover_containers() -> bool:
    listed = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=darwin.run"], capture_output=True, text=True,
        check=True,
    )  # fmt: skip
    return listed.stdout.strip() == ""


async def test_perft_accepts_a_correct_generator(settings: Settings) -> None:
    result = await perft_gate(settings, engines.random_player(settings), seed=1, positions=3)
    assert result.passed, result.detail
    assert no_leftover_containers()


async def test_perft_points_at_the_wrong_move(settings: Settings) -> None:
    result = await perft_gate(settings, faulty("bad_perft"), seed=1, positions=3)
    assert not result.passed
    assert result.detail["problem"] == "wrong_count"
    assert result.detail["got"] == result.detail["expected"] + 1


async def test_perft_reports_a_silent_engine(settings: Settings) -> None:
    result = await perft_gate(settings, faulty("timeout"), seed=1, positions=1, depth=1)
    assert result.passed  # perft itself answers; the timeout engine only hangs on `go`


async def test_smoke_passes_a_legal_player(settings: Settings) -> None:
    candidate = engines.random_player(settings)
    opponent = faulty("greedy")
    result = await smoke_gate(settings, candidate, opponent, FAST, seed=2)
    assert result.passed, result.detail
    assert result.detail["games"] == 4


@pytest.mark.parametrize(
    ("mode", "problem"),
    [("illegal", "illegal_move"), ("crash", "crash"), ("timeout", "timeout")],
)
async def test_smoke_catches_contract_breakers(settings: Settings, mode: str, problem: str) -> None:
    result = await smoke_gate(settings, faulty(mode), engines.random_player(settings), FAST, seed=3)
    assert result.gate is Gate.SMOKE
    assert not result.passed
    assert result.detail["problem"] == problem
    assert "[White" in result.detail["pgn"]
    assert no_leftover_containers()


async def test_sprt_accepts_a_clearly_stronger_engine(settings: Settings) -> None:
    gate, match = await match_gate(
        settings, faulty("greedy"), engines.random_player(settings), VS_RANDOM, seed=4
    )
    assert gate.passed, gate.detail
    assert gate.detail["verdict"] == "h1"
    assert match.elo > 0
    assert len(match.games) % 2 == 0


async def test_sprt_rejects_a_clearly_weaker_engine(settings: Settings) -> None:
    gate, _ = await match_gate(
        settings, engines.random_player(settings), faulty("greedy"), VS_RANDOM, seed=5
    )
    assert not gate.passed
    assert gate.detail["verdict"] == "h0"


async def test_stockfish_anchor_rates_a_weak_engine_below_the_ladder(settings: Settings) -> None:
    from darwin.referee.rating import rate

    rating = await rate(settings, faulty("greedy"), pairs=3, tc="2+0.02", seed=6)
    assert rating.below_scale  # mate-in-one and greed do not trouble Stockfish 1320
    assert rating.anchors[0].anchor_elo == 1320 and rating.anchors[0].score < 0.1
