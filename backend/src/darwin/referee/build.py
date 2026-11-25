"""Build gate: a clean release build of one genome commit, offline, in a fresh container.

The build starts from the trusted mirror (`refs/darwin/*`), never from the agent's working
tree or repository, so what is judged is exactly what was archived. The binary is kept
under the data dir by commit.
"""

import re
import time

from darwin.config import Settings
from darwin.referee import docker
from darwin.referee.errors import RefereeError
from darwin.referee.models import Binary, Gate, GateResult

COMMIT = re.compile(r"^[0-9a-f]{40}$")
LOG_TAIL_LINES = 40

SCRIPT = """
set -e
git init -q /tmp/build
cd /tmp/build
git -c safe.directory='*' fetch -q /src '+refs/darwin/*:refs/darwin/*'
git -c advice.detachedHead=false checkout -q --detach "$1"
cargo build --release --offline --quiet
cp /tmp/target/release/genome /out/genome
"""


def binary_for(settings: Settings, commit: str) -> Binary:
    return Binary(commit, settings.data_dir / "binaries" / commit)


def build_argv(settings: Settings, commit: str, out: Binary, run_id: str) -> list[str]:
    return [
        settings.docker_bin, "run", "--rm",
        "--network", "none",
        "--cpus", str(settings.build_cpus), "--memory", settings.build_memory,
        "--read-only", "--tmpfs", "/tmp:exec,size=4g",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "1000:1000",
        "--label", f"{docker.RUN_LABEL}={run_id}",
        "-e", "CARGO_HOME=/tmp/cargo", "-e", "CARGO_TARGET_DIR=/tmp/target",
        "-v", f"{settings.mirror_dir}:/src:ro",
        "-v", f"{out.dir}:/out",
        settings.lab_image, "sh", "-c", SCRIPT, "build", commit,
    ]  # fmt: skip


async def build_gate(settings: Settings, commit: str) -> tuple[GateResult, Binary | None]:
    if not COMMIT.match(commit):
        raise RefereeError(f"not a full commit sha: {commit!r}")
    out = binary_for(settings, commit)
    if out.path.is_file():  # same commit, same build: reuse it
        return GateResult(Gate.BUILD, True, {"cached": True}, 0), out
    out.dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    run_id = docker.new_run_id()
    try:
        done = await docker.run(build_argv(settings, commit, out, run_id), settings.build_timeout_s)
    finally:
        await docker.remove_run_containers(settings, run_id)
    elapsed = int((time.monotonic() - started) * 1000)
    if done.returncode == 125:  # docker itself failed, not the build
        raise RefereeError(f"docker could not start the build: {done.stderr.strip()}")
    if done.timed_out or done.returncode != 0 or not out.path.is_file():
        tail = "\n".join(done.stderr.strip().splitlines()[-LOG_TAIL_LINES:])
        problem = "timeout" if done.timed_out else "build_failed"
        return GateResult(Gate.BUILD, False, {"problem": problem, "log": tail}, elapsed), None
    return GateResult(Gate.BUILD, True, {"cached": False}, elapsed), out
