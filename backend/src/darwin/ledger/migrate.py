"""Applies the ledger migrations. Called by core at startup: the schema it runs on is
always the one the code expects, whatever was deployed before."""

from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[3]


def migrate(url: str) -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
