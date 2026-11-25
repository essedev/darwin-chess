import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.ledger.migrate import migrate
from darwin.ledger.store import Ledger


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
