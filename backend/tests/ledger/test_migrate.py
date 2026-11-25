import logging
from pathlib import Path

from darwin.ledger.migrate import migrate


def test_migrating_keeps_the_application_logging(tmp_path: Path) -> None:
    root = logging.getLogger()
    before = (root.level, list(root.handlers))
    root.setLevel(logging.INFO)
    try:
        migrate(f"sqlite+aiosqlite:///{tmp_path / 'ledger.sqlite'}")
        assert root.level == logging.INFO  # alembic.ini would have set WARNING
    finally:
        root.setLevel(before[0])
