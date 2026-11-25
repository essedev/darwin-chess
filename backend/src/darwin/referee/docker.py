"""Thin async wrapper around the Docker CLI: engine containers, one-shot runs, cleanup.

Every container the referee starts carries the label `darwin.run=<run id>`, so whatever a
run leaves behind (an engine stuck in an infinite loop survives its client) is removed by
label when the run ends.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass

from darwin.config import Settings
from darwin.referee.errors import RefereeError
from darwin.referee.models import EngineSpec

log = logging.getLogger(__name__)

RUN_LABEL = "darwin.run"
INSTANCE_LABEL = "darwin.instance"  # which core started it: a restart cleans up its own


def labels(settings: Settings, run_id: str) -> list[str]:
    return ["--label", f"{RUN_LABEL}={run_id}", "--label", f"{INSTANCE_LABEL}={settings.instance}"]


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def engine_argv(settings: Settings, spec: EngineSpec, run_id: str) -> list[str]:
    """`docker run` for one engine: no network, one CPU, read-only, no privileges."""
    argv = [
        settings.docker_bin, "run", "--rm", "-i", "--init",
        "--network", "none",
        "--cpus", str(settings.engine_cpus),
        "--memory", settings.engine_memory,
        "--pids-limit", "64",
        "--read-only", "--tmpfs", "/tmp:size=64m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        *labels(settings, run_id),
    ]  # fmt: skip
    for mount in spec.mounts:
        argv += ["-v", f"{mount.host}:{mount.container}:ro"]
    return [*argv, spec.image, *spec.command]


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool


async def run(argv: list[str], timeout_s: float) -> Completed:
    """Run a command to completion; on timeout kill it and report `timed_out`."""
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), timeout_s)
    except TimeoutError:
        process.kill()
        out, err = await process.communicate()
        return Completed(-1, out.decode(errors="replace"), err.decode(errors="replace"), True)
    assert process.returncode is not None
    return Completed(process.returncode, out.decode(errors="replace"), err.decode(errors="replace"),
                     False)  # fmt: skip


async def remove_run_containers(settings: Settings, run_id: str) -> None:
    listed = await run(
        [settings.docker_bin, "ps", "-aq", "--filter", f"label={RUN_LABEL}={run_id}"], 30
    )
    if listed.returncode != 0:
        raise RefereeError(f"docker ps failed: {listed.stderr.strip()}")
    ids = listed.stdout.split()
    if not ids:
        return
    removed = await run([settings.docker_bin, "rm", "-f", *ids], 60)
    if removed.returncode != 0 and not only_going(removed.stderr):
        raise RefereeError(f"docker rm failed: {removed.stderr.strip()}")
    log.info("removed %d leftover containers of run %s", len(ids), run_id)


async def remove_instance_containers(settings: Settings) -> int:
    """Everything a previous run of this instance left behind (it crashed or was stopped
    mid-match): arenas, engines, sandboxes, builds. Returns how many were removed."""
    listed = await run(
        [settings.docker_bin, "ps", "-aq", "--filter",
         f"label={INSTANCE_LABEL}={settings.instance}"],
        30,
    )  # fmt: skip
    if listed.returncode != 0:
        raise RefereeError(f"docker ps failed: {listed.stderr.strip()}")
    ids = listed.stdout.split()
    if ids:
        removed = await run([settings.docker_bin, "rm", "-f", *ids], 120)
        if removed.returncode != 0 and not only_going(removed.stderr):
            raise RefereeError(f"docker rm failed: {removed.stderr.strip()}")
    return len(ids)


# Containers started with --rm remove themselves when their process dies: right after a stop
# Docker may be removing them already, or be done. Neither is a failure to remove them.
GOING = ("is already in progress", "No such container")


def only_going(stderr: str) -> bool:
    """True when every error `docker rm` printed is about a container already going away."""
    errors = [line for line in stderr.splitlines() if line.strip()]
    return bool(errors) and all(any(mark in line for mark in GOING) for line in errors)
