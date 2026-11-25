from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.referee.models import EngineSpec

TEST_ENGINES_IMAGE = "darwin-testengines"


@pytest.fixture
def settings(tmp_path: Path, images: None) -> Settings:
    return Settings(data_dir=tmp_path / "data", genome_dir=tmp_path / "genome",
                    mirror_dir=tmp_path / "mirror.git", match_concurrency=3)  # fmt: skip


def faulty(mode: str, name: str | None = None) -> EngineSpec:
    return EngineSpec(
        name=name or mode,
        image=TEST_ENGINES_IMAGE,
        command=("python3", "/anchors/faulty_engine.py", mode),
    )
