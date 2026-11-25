"""Plays a match with fastchess in the `arena` container and reads it back.

fastchess starts each engine through a wrapper script that runs `docker run` on the host
daemon, so every engine lives in its own container. The referee then trusts nothing it did
not check: it replays every PGN with python-chess and derives how each game ended.
"""

import json
import logging
import shlex
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn

from darwin.config import Settings
from darwin.referee import docker
from darwin.referee.errors import RefereeError
from darwin.referee.models import EngineSpec, GameRecord, Termination

log = logging.getLogger(__name__)

FAULT_TERMINATIONS = {
    "illegal_move": Termination.ILLEGAL_MOVE,
    "time_forfeit": Termination.TIMEOUT,
    "stall": Termination.TIMEOUT,
    "disconnect": Termination.CRASH,
    "adjudication": Termination.ADJUDICATION,
}
MAX_MOVES = 300  # adjudicated draw: weak engines can shuffle for a very long time


@dataclass(frozen=True)
class MatchPlan:
    a: EngineSpec
    b: EngineSpec
    openings: list[str]  # EPD; each is played twice with colours swapped
    tc: str  # fastchess format, e.g. "8+0.08"
    concurrency: int


def _seconds(tc: str) -> tuple[float, float]:
    base, _, inc = tc.partition("+")
    return float(base), float(inc or 0)


def timeout_for(plan: MatchPlan) -> float:
    base, inc = _seconds(plan.tc)
    per_game = 2 * (base + inc * MAX_MOVES) + 30  # both clocks fully used, plus startup
    games = 2 * len(plan.openings)
    return games * per_game / plan.concurrency + 120


def _wrapper(settings: Settings, spec: EngineSpec, run_id: str) -> str:
    # Runs inside the arena image, where the CLI is `docker` on PATH whatever the host uses,
    # behind the shim that kills a container ignoring `quit`.
    argv = ["docker", *docker.engine_argv(settings, spec, run_id)[1:]]
    shim = ["python3", "/usr/local/bin/engine_shim.py", f"darwin-{run_id}-{spec.name}"]
    return f"#!/bin/sh\nexec {shlex.join([*shim, *argv])}\n"


def _options(spec: EngineSpec) -> list[str]:
    return [f"option.{name}={value}" for name, value in spec.options]


def arena_argv(settings: Settings, plan: MatchPlan, run_id: str, workdir: Path) -> list[str]:
    return [
        settings.docker_bin, "run", "--rm", "--name", f"darwin-arena-{run_id}",
        "--label", f"{docker.RUN_LABEL}={run_id}",
        "-v", f"{settings.docker_socket}:/var/run/docker.sock",
        "-v", f"{workdir}:{workdir}", "-w", str(workdir),
        settings.arena_image,
        "-engine", f"name={plan.a.name}", f"cmd={workdir / 'a.sh'}", *_options(plan.a),
        "-engine", f"name={plan.b.name}", f"cmd={workdir / 'b.sh'}", *_options(plan.b),
        "-each", f"tc={plan.tc}", "proto=uci",
        "-rounds", str(len(plan.openings)), "-repeat",
        "-concurrency", str(plan.concurrency),
        "-openings", "file=book.epd", "format=epd", "order=sequential",
        "-maxmoves", str(MAX_MOVES),
        "-pgnout", "file=games.pgn", "-events", "file=events.ndjson",
        "-recover", "-ratinginterval", "0", "-autosaveinterval", "0",
        "-startup-ms", "20000", "-ping-ms", "5000", "-ucinewgame-ms", "10000",
    ]  # fmt: skip


async def play(settings: Settings, plan: MatchPlan) -> list[GameRecord]:
    if plan.a.name == plan.b.name:
        raise RefereeError(f"both engines are named {plan.a.name!r}")
    run_id = docker.new_run_id()
    workdir = settings.data_dir / "matches" / run_id
    workdir.mkdir(parents=True)
    (workdir / "book.epd").write_text("\n".join(plan.openings) + "\n")
    for filename, spec in (("a.sh", plan.a), ("b.sh", plan.b)):
        script = workdir / filename
        script.write_text(_wrapper(settings, spec, run_id))
        script.chmod(0o755)
    try:
        done = await docker.run(arena_argv(settings, plan, run_id, workdir), timeout_for(plan))
    finally:
        await docker.remove_run_containers(settings, run_id)
    if done.timed_out:
        raise RefereeError(f"match {run_id} exceeded {timeout_for(plan):.0f}s")
    if done.returncode != 0:
        raise RefereeError(f"fastchess exited {done.returncode}: {done.stderr[-2000:]}")
    games = read_games(workdir)
    if len(games) != 2 * len(plan.openings):
        raise RefereeError(f"match {run_id}: {len(games)} games, {2 * len(plan.openings)} planned")
    log.info("match %s: %d games", run_id, len(games))
    return games


def read_games(workdir: Path) -> list[GameRecord]:
    finished: dict[int, dict[str, object]] = {}
    for line in (workdir / "events.ndjson").read_text().splitlines():
        event = json.loads(line)
        if event.get("event") == "game_finished":
            finished[int(event["pgn_game_id"])] = event
    games: list[GameRecord] = []
    with (workdir / "games.pgn").open() as handle:
        while (game := chess.pgn.read_game(handle)) is not None:
            game_id = int(game.headers["GameId"])
            if game_id not in finished:
                raise RefereeError(f"game {game_id} has no game_finished event")
            games.append(verify(game, str(finished[game_id]["termination"])))
    return games


def verify(game: chess.pgn.Game, termination: str) -> GameRecord:
    """Replays the game and returns it with the termination the referee can vouch for."""
    if game.errors:
        raise RefereeError(f"unreadable game {game.headers.get('GameId')}: {game.errors[0]}")
    result = game.headers["Result"]
    board = game.end().board()
    if termination == "normal":
        derived = _natural_end(board, result)
    elif termination in FAULT_TERMINATIONS:
        derived = FAULT_TERMINATIONS[termination]
        decisive = result in {"1-0", "0-1"}
        if (derived is Termination.ADJUDICATION) == decisive:
            raise RefereeError(f"{termination} with result {result}")
    else:
        raise RefereeError(f"game {game.headers.get('GameId')} ended as {termination!r}")
    return GameRecord(
        white=game.headers["White"],
        black=game.headers["Black"],
        result=result,
        termination=derived,
        start_fen=game.board().fen(),
        pgn=str(game),
    )


def _natural_end(board: chess.Board, result: str) -> Termination:
    if board.is_checkmate():
        expected = "0-1" if board.turn == chess.WHITE else "1-0"
        if result != expected:
            raise RefereeError(f"checkmate scored {result}")
        return Termination.CHECKMATE
    if result != "1/2-1/2":
        raise RefereeError(f"decisive result {result} without checkmate")
    if board.is_stalemate():
        return Termination.STALEMATE
    if board.is_insufficient_material():
        return Termination.MATERIAL
    if board.is_fifty_moves():
        return Termination.FIFTY_MOVES
    if board.is_repetition(3):
        return Termination.REPETITION
    raise RefereeError(f"draw without a rule that ends it: {board.fen()}")
