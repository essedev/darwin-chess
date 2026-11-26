import logging
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from darwin.ledger.migrate import BACKEND, migrate


def test_migrating_keeps_the_application_logging(tmp_path: Path) -> None:
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    root.setLevel(logging.INFO)
    try:
        migrate(f"sqlite+aiosqlite:///{tmp_path / 'ledger.sqlite'}")
        assert root.level == logging.INFO  # alembic.ini would have set WARNING
    finally:
        root.setLevel(before[0])


def test_past_haiku_calls_get_their_cache_writes_back_from_the_cost(tmp_path: Path) -> None:
    db = tmp_path / "ledger.sqlite"
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db}")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "51c28e2e58a0")  # the revision before the column
    # 300 input, 900 cache read, 50 output and 2,000 cache writes, at pi's Haiku 5.5 prices.
    cost = 300 * 0.10e-6 + 900 * 0.01e-6 + 50 * 0.50e-6 + 2000 * 0.125e-6
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO generations (id, commit_sha, created_at) VALUES (0, ?, ?)",
                     ("0" * 40, "2026-11-25 10:00:00"))  # fmt: skip
        conn.execute(
            "INSERT INTO experiments (id, kind, phase, status, base_commit, base_generation_id,"
            " trigger, created_at) VALUES (1, 'iteration', 'evolution', 'accepted', ?, 0,"
            " 'start', '2026-11-25 10:00:00')",
            ("0" * 40,),
        )
        for model in ("claude-haiku-5-5", "other-model"):
            conn.execute(
                "INSERT INTO llm_calls (experiment_id, model, input_tokens, cached_tokens,"
                " output_tokens, cost_usd, created_at) VALUES (1, ?, 300, 900, 50, ?, ?)",
                (model, cost, "2026-11-25 10:00:00"),
            )
    migrate(f"sqlite+aiosqlite:///{db}")
    with sqlite3.connect(db) as conn:
        rows = dict(conn.execute("SELECT model, cache_write_tokens FROM llm_calls"))
    assert rows == {"claude-haiku-5-5": 2000, "other-model": 0}  # unknown prices: left at 0
