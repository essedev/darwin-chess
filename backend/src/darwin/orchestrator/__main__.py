"""`python -m darwin.orchestrator [--sessions N]`: runs the experiment (core service)."""

import argparse
import asyncio
import logging

from darwin.config import get_settings
from darwin.ledger.migrate import migrate
from darwin.ledger.store import Ledger
from darwin.orchestrator.loop import Orchestrator


async def main(sessions: int | None) -> None:
    settings = get_settings()
    if not settings.llm_api_key.get_secret_value():
        raise SystemExit("DARWIN_LLM_API_KEY is not set")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(migrate, settings.ledger_url)
    ledger = Ledger(settings.ledger_url)
    try:
        await Orchestrator(settings, ledger).run(max_sessions=sessions)
    finally:
        await ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, help="stop after N sessions (test runs)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    asyncio.run(main(args.sessions))
