"""`python -m darwin.orchestrator [--sessions N | --lichess-games N]`: runs the experiment
(core service), a few trial sessions, or only the Lichess bot for a few games."""

import argparse
import asyncio
import logging
import signal

from darwin.config import PROVIDERS, get_settings
from darwin.ledger.migrate import migrate
from darwin.ledger.store import Ledger
from darwin.orchestrator.loop import Orchestrator


async def main(sessions: int | None, lichess_games: int | None) -> None:
    # A stop (SIGTERM from Docker, Ctrl-C) cancels this task, so every finally runs: tasks
    # cancelled, clients closed, this run's containers removed. Unhandled, SIGTERM kills the
    # process on the spot.
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    assert task is not None
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, task.cancel)
    settings = get_settings()
    needs_model = lichess_games is None
    if (
        needs_model
        and settings.llm_provider in PROVIDERS
        and not settings.llm_api_key.get_secret_value()
    ):
        raise SystemExit(f"DARWIN_LLM_API_KEY is not set (provider {settings.llm_provider})")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(migrate, settings.ledger_url)
    ledger = Ledger(settings.ledger_url)
    try:
        orchestrator = Orchestrator(settings, ledger)
        if lichess_games is not None:
            await orchestrator.run_lichess_only(lichess_games)
        else:
            await orchestrator.run(max_sessions=sessions)
    finally:
        await ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    runs = parser.add_mutually_exclusive_group()
    runs.add_argument("--sessions", type=int, help="stop after N sessions (test runs)")
    runs.add_argument("--lichess-games", type=int, help="only the Lichess bot, for N games")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        asyncio.run(main(args.sessions, args.lichess_games))
    except asyncio.CancelledError:
        logging.getLogger(__name__).info("stopped")
