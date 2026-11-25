import subprocess
import uuid
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.referee.docker import remove_instance_containers

pytestmark = pytest.mark.docker


def start(labels: list[str]) -> str:
    args = [arg for label in labels for arg in ("--label", label)]
    done = subprocess.run(["docker", "run", "-d", "--rm", *args, "darwin-anchors", "sleep", "60"],
                          capture_output=True, text=True, check=True)  # fmt: skip
    return done.stdout.strip()


def alive(container: str) -> bool:
    done = subprocess.run(["docker", "ps", "-q", "--no-trunc", "--filter", f"id={container}"],
                          capture_output=True, text=True, check=True)  # fmt: skip
    return done.stdout.strip() != ""


def remove(*containers: str) -> None:
    subprocess.run(["docker", "rm", "-f", *containers], capture_output=True, check=False)


async def test_startup_cleanup_removes_only_its_own_instance(tmp_path: Path, images: None) -> None:
    mine, other = f"test-{uuid.uuid4().hex[:8]}", f"test-{uuid.uuid4().hex[:8]}"
    leftover = start(["darwin.run=x", f"darwin.instance={mine}"])
    foreign = start(["darwin.run=y", f"darwin.instance={other}"])
    try:
        settings = Settings(data_dir=tmp_path, instance=mine)
        assert await remove_instance_containers(settings) == 1
        assert not alive(leftover)
        assert alive(foreign)
    finally:
        remove(leftover, foreign)
