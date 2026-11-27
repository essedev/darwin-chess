"""The daily copy of the SQLite ledger, made while it is open."""

import os
import sqlite3
import time
from pathlib import Path

from darwin.ledger import backup
from darwin.ledger.store import Ledger


def test_the_ledger_file_comes_from_a_sqlite_url_only() -> None:
    assert backup.ledger_file("sqlite+aiosqlite:////ledger/ledger.sqlite") == Path(
        "/ledger/ledger.sqlite"
    )
    assert backup.ledger_file("postgresql+asyncpg://u@h/db") is None


async def test_the_copy_holds_what_the_open_ledger_holds(
    tmp_path: Path, ledger_url: str, ledger: Ledger
) -> None:
    await ledger.seed("a" * 40)  # the ledger stays open, as in core
    source = backup.ledger_file(ledger_url)
    assert source is not None
    target = tmp_path / "data" / "backup" / "ledger.sqlite"
    backup.copy(source, target)
    with sqlite3.connect(target) as copied:
        (commit,) = copied.execute("select commit_sha from generations").fetchone()
    assert commit == "a" * 40
    assert not target.with_suffix(".partial").exists()


def test_a_copy_is_due_when_missing_or_a_day_old(tmp_path: Path) -> None:
    target = tmp_path / "ledger.sqlite"
    assert backup.due(target, 86400)
    target.write_bytes(b"")
    assert not backup.due(target, 86400)
    day_ago = time.time() - 86400
    os.utime(target, (day_ago, day_ago))
    assert backup.due(target, 86400)
