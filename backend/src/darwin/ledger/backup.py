"""A consistent copy of the SQLite ledger in `data/backup/ledger.sqlite`, refreshed every day.

In Compose the ledger lives in a Docker volume, out of reach of a host backup and lost with
the volume; the copy sits in the data folder, where the host's backup picks it up. SQLite's
online backup makes it while core keeps writing, so it is never a half-written file.
"""

import asyncio
import logging
import os
import sqlite3
import time
from pathlib import Path

from sqlalchemy.engine import make_url

from darwin.config import Settings

log = logging.getLogger(__name__)

CHECK_EVERY_S = 3600.0


def ledger_file(url: str) -> Path | None:
    """The database file behind a SQLite URL; None for any other database."""
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return None
    return Path(parsed.database)


def backup_file(settings: Settings) -> Path:
    return settings.data_dir / "backup" / "ledger.sqlite"


def copy(source: Path, target: Path) -> None:
    """Copies the database through SQLite's backup API, then swaps the file in at once."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    partial.unlink(missing_ok=True)
    # Not read-only: in WAL mode a reader writes the shared index too.
    src, dst = sqlite3.connect(source), sqlite3.connect(partial)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    os.replace(partial, target)


def due(target: Path, every_s: float, now: float | None = None) -> bool:
    if not target.exists():
        return True
    return (now if now is not None else time.time()) - target.stat().st_mtime >= every_s


async def run(settings: Settings) -> None:
    """Core's task: a fresh copy whenever the last one is a day old, checked every hour."""
    source = ledger_file(settings.ledger_url)
    if source is None:
        log.info("ledger backup: not a SQLite ledger, nothing to copy")
        return
    target = backup_file(settings)
    every_s = settings.ledger_backup_every_h * 3600
    while True:
        if due(target, every_s):
            try:
                await asyncio.to_thread(copy, source, target)
                log.info("ledger backup: copied to %s", target)
            except Exception:
                log.exception("ledger backup failed, retrying in an hour")
        await asyncio.sleep(CHECK_EVERY_S)
