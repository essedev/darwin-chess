from typing import Any, cast

from darwin.config import Settings
from darwin.ledger import lichess
from darwin.ledger.store import Ledger
from darwin.orchestrator.jobs import Jobs
from darwin.orchestrator.sandbox import Sandbox
from darwin.orchestrator.tools import SessionTools

SHUFFLE = "g1f3 g8f6 f3g1 f6g8 "  # four plies; any moves do, the tool does not replay them
FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


def tools(ledger: Ledger) -> SessionTools:
    # This tool only reads the ledger: no sandbox, no jobs.
    return SessionTools(
        Settings(), ledger, cast(Jobs, None), cast(Sandbox, None), 1, "0" * 40, None
    )


async def play(
    ledger: Ledger,
    lichess_id: str,
    result: str,
    moves: str,
    analysis: dict[str, Any] | None = None,
    **game: Any,
) -> None:
    fields: dict[str, Any] = {
        "generation_id": 0,
        "color": "white",
        "opponent": "someone",
        "opponent_rating": 1500,
        "opponent_title": None,
        "rated": True,
        "time_control": "3+2",
    }
    await lichess.start_game(ledger, lichess_id=lichess_id, **(fields | game))
    game_id = await lichess.finish_game(
        ledger, lichess_id, status="mate", result=result, moves=moves, rating_after=1450
    )
    if analysis is not None:
        await lichess.set_analysis(ledger, game_id, analysis)


async def test_without_losses_it_says_so(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    await play(ledger, "won00001", "win", "e2e4 e7e5")
    assert await tools(ledger).call("lichess_losses", {}) == "No Lichess losses yet."


async def test_each_loss_points_at_its_worst_move_and_keeps_the_tail_of_the_game(
    ledger: Ledger,
) -> None:
    await ledger.seed("0" * 40)
    analysis = {
        "move_number": 23,
        "move": "Nxe5",
        "eval_before_cp": 40,
        "eval_after_cp": -210,
        "drop_cp": 250,
        "fen_before": FEN,
    }
    await play(
        ledger,
        "long0001",
        "loss",
        (SHUFFLE * 12 + "e2e4 e7e5 d2d4").strip(),  # 51 plies
        analysis,
        opponent="Magnus",
        opponent_title="GM",
        opponent_rating=2850,
    )
    await play(ledger, "short001", "loss", "f2f3 e7e5 g2g4 d8h4", color="black", rated=False)
    await play(ledger, "won00001", "win", "e2e4 e7e5")

    text = await tools(ledger).call("lichess_losses", {"limit": 5})

    head, short, long = text.split("\n\n")
    assert head == "2 most recent Lichess loss(es), newest first."
    assert short.splitlines() == [
        "Game short001 (gen-0): you were black against someone (1500), 3+2 casual, "
        "ended (mate) after 2 moves.",
        "  Worst move: not analysed.",
        "  Moves (UCI): f2f3 e7e5 g2g4 d8h4",
    ]
    first, worst, moves = long.splitlines()
    assert first == (
        "Game long0001 (gen-0): you were white against GM Magnus (2850), 3+2 rated, "
        "ended (mate) after 26 moves."
    )
    assert worst == (
        "  Worst move: move 23 (Nxe5): your evaluation went from +0.4 to -2.1, "
        f"position before: {FEN}"
    )
    assert moves.startswith("  Moves (UCI, last 40 of 51 plies): ... ")
    assert len(moves.split(": ... ")[1].split()) == 40
    assert moves.endswith("e2e4 e7e5 d2d4")


async def test_a_mate_is_named_and_the_limit_is_respected(ledger: Ledger) -> None:
    await ledger.seed("0" * 40)
    mated = {
        "move_number": 3,
        "move": "Kf2",
        "eval_before_cp": 0,
        "eval_after_cp": -10000,
        "drop_cp": 10000,
        "fen_before": FEN,
    }
    for n in range(3):
        await play(ledger, f"loss000{n}", "loss", "e2e4", mated)

    text = await tools(ledger).call("lichess_losses", {"limit": 2})

    assert text.count("Game loss000") == 2 and "loss0000" not in text  # newest first
    assert "went from +0.0 to a forced mate against you" in text
