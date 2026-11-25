import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from darwin.config import Settings
from darwin.ledger.store import Ledger

BACKEND = Path(__file__).resolve().parents[1]


def migrate(url: str) -> None:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture
def ledger_url(tmp_path: Path) -> str:
    """A real SQLite ledger built by the real migrations."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'ledger.sqlite'}"
    migrate(url)
    return url


@pytest.fixture
async def ledger(ledger_url: str) -> AsyncIterator[Ledger]:
    store = Ledger(ledger_url)
    yield store
    await store.close()


@pytest.fixture(scope="session")
def images() -> None:
    """Docker tests run against the real images; build them with `make images`."""
    settings = Settings()
    names = (settings.lab_image, settings.arena_image, settings.anchors_image, "darwin-testengines")
    for image in names:
        found = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
        if found.returncode != 0:
            pytest.fail(f"image {image} missing: run `make images`")
