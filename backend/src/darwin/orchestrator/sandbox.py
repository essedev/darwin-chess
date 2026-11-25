"""The agent's sandbox: one container per session, and the git operations on the genome.

The genome repository belongs to the agent, hooks and config included, so git never runs
on it from the host: every git command runs in a container. The champion lineage lives in
a trusted bare mirror that only the orchestrator writes; the build gate clones from it.
"""

import logging
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from darwin.config import Settings
from darwin.referee import docker

log = logging.getLogger(__name__)

SHA = re.compile(r"^[0-9a-f]{40}$")
AGENT_GIT = ["-c", "user.name=darwin-agent", "-c", "user.email=agent@darwin.local",
             "-c", "safe.directory=*"]  # fmt: skip


class SandboxError(Exception):
    pass


@dataclass(frozen=True)
class ExecResult:
    code: int
    output: str


def _check_sha(value: str) -> str:
    if not SHA.match(value):
        raise SandboxError(f"not a commit sha: {value!r}")
    return value


def _git(*args: str) -> str:
    return shlex.join(["git", *AGENT_GIT, *args])


async def helper(settings: Settings, script: str, *, genome_rw: bool = False,
                 extra_mounts: list[tuple[Path, str]] | None = None,
                 timeout_s: float = 300) -> ExecResult:  # fmt: skip
    """A one-shot trusted container on the genome (read-only by default) and the mirror."""
    run_id = docker.new_run_id()
    genome_mode = "rw" if genome_rw else "ro"
    mounts = [f"{settings.genome_dir}:/genome:{genome_mode}", f"{settings.mirror_dir}:/mirror"]
    mounts += [f"{host}:{inside}" for host, inside in extra_mounts or []]
    argv = [
        settings.docker_bin, "run", "--rm", "--network", "none", "--user", "1000:1000",
        "--read-only", "--tmpfs", "/tmp:exec,size=2g", "-e", "HOME=/tmp",
        "--label", f"{docker.RUN_LABEL}={run_id}",
        *[arg for mount in mounts for arg in ("-v", mount)],
        settings.lab_image, "sh", "-ec", script,
    ]  # fmt: skip
    try:
        done = await docker.run(argv, timeout_s)
    finally:
        await docker.remove_run_containers(settings, run_id)
    return ExecResult(done.returncode, (done.stdout + done.stderr).strip())


async def init_mirror(settings: Settings) -> str:
    """Creates the mirror from the genome's gen-0 once; returns the gen-0 commit."""
    settings.mirror_dir.mkdir(parents=True, exist_ok=True)
    script = f"""
test -f /mirror/HEAD || git init -q --bare /mirror
sha=$({_git("-C", "/genome", "rev-parse", "gen-0^{commit}")})
{_git("-C", "/mirror", "fetch", "-q", "/genome", "gen-0")}
{_git("-C", "/mirror", "update-ref", "refs/darwin/gen-0", "FETCH_HEAD")}
echo "$sha"
"""
    done = await helper(settings, script)
    if done.code != 0:
        raise SandboxError(f"cannot initialise the mirror: {done.output}")
    return _check_sha(done.output.splitlines()[-1])


def update_ref_script(ref: str, sha: str) -> str:
    if not re.match(r"^[a-z0-9-]+$", ref):
        raise SandboxError(f"bad ref name {ref!r}")
    return _git("-C", "/mirror", "update-ref", f"refs/darwin/{ref}", _check_sha(sha))


async def archive(settings: Settings, sha: str, ref: str) -> None:
    """Copies a commit from the agent's repository into the mirror under `refs/darwin/<ref>`."""
    if not re.match(r"^[a-z0-9-]+$", ref):
        raise SandboxError(f"bad ref name {ref!r}")
    # The commit is the agent's detached HEAD right after `commit_all`: fetch HEAD (always
    # advertised) and check it is the expected one before naming it.
    script = f"""
{_git("-C", "/mirror", "fetch", "-q", "/genome", "HEAD")}
test "$(git -C /mirror rev-parse FETCH_HEAD)" = {_check_sha(sha)}
{_git("-C", "/mirror", "update-ref", f"refs/darwin/{ref}", sha)}
"""
    done = await helper(settings, script)
    if done.code != 0:
        raise SandboxError(f"cannot archive {sha}: {done.output}")


async def rebase(settings: Settings, sha: str, old_base: str, new_base: str,
                 ref: str) -> str | None:  # fmt: skip
    """Replays a candidate made on `old_base` onto `new_base`; None on conflict."""
    script = f"""
git init -q /tmp/w
cd /tmp/w
{_git("fetch", "-q", "/mirror", "+refs/darwin/*:refs/darwin/*")}
{_git("checkout", "-q", "--detach", _check_sha(sha))}
if {_git("rebase", "-q", "--onto", _check_sha(new_base), _check_sha(old_base))}; then
  {_git("push", "-q", "/mirror", f"HEAD:refs/darwin/{ref}")}
  git rev-parse HEAD
else
  echo conflict
fi
"""
    done = await helper(settings, script)
    last = done.output.splitlines()[-1] if done.output else ""
    if done.code != 0:
        raise SandboxError(f"rebase failed to run: {done.output}")
    return last if SHA.match(last) else None


class Sandbox:
    """The container where every tool call of one agent session runs."""

    def __init__(self, settings: Settings, experiment_id: int) -> None:
        self.settings = settings
        self.name = f"darwin-sandbox-{experiment_id}-{docker.new_run_id()[:6]}"
        self.run_id = docker.new_run_id()

    async def start(self) -> None:
        s = self.settings
        (s.data_dir / "jobs").mkdir(parents=True, exist_ok=True)
        memory = s.data_dir / "agent" / "memory"
        argv = [
            s.docker_bin, "run", "-d", "--name", self.name, "--init",
            "--network", "none", "--cpus", str(s.build_cpus), "--memory", s.build_memory,
            "--pids-limit", "512", "--read-only", "--tmpfs", "/tmp:exec,size=2g",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000",
            "-e", "HOME=/tmp", "-e", "CARGO_HOME=/tmp/cargo",
            "--label", f"{docker.RUN_LABEL}={self.run_id}",
            "-v", f"{s.genome_dir}:/genome", "-v", f"{s.mirror_dir}:/mirror:ro",
            "-v", f"{s.data_dir / 'jobs'}:/jobs:ro", "-v", f"{memory}:/memory",
            "-w", "/genome",
            s.lab_image, "sleep", "infinity",
        ]  # fmt: skip
        done = await docker.run(argv, 120)
        if done.returncode != 0:
            raise SandboxError(f"sandbox did not start: {done.stderr.strip()}")

    async def stop(self) -> None:
        await docker.remove_run_containers(self.settings, self.run_id)

    async def exec(self, script: str, timeout_s: float = 300) -> ExecResult:
        argv = [self.settings.docker_bin, "exec", self.name, "sh", "-ec", script]
        done = await docker.run(argv, timeout_s + 5)
        if done.timed_out:
            return ExecResult(-1, "timed out")
        return ExecResult(done.returncode, (done.stdout + done.stderr).strip())

    async def reset_to(self, base: str) -> None:
        """Working tree = `base`, whatever the agent left behind. Build cache survives."""
        script = f"""
test -d /genome/.git || git init -q /genome
{_git("-C", "/genome", "fetch", "-q", "/mirror", "+refs/darwin/*:refs/darwin/*")}
{_git("-C", "/genome", "checkout", "-q", "-f", "--detach", _check_sha(base))}
{_git("-C", "/genome", "clean", "-q", "-fdx", "-e", "target")}
"""
        done = await self.exec(script)
        if done.code != 0:
            raise SandboxError(f"cannot reset the genome to {base}: {done.output}")

    async def commit_all(self, message: str, base: str) -> str | None:
        """Commits what is left in the working tree on top of whatever the agent committed
        itself; returns HEAD, or None when HEAD is still `base` (nothing to judge)."""
        script = f"""
cd /genome
{_git("add", "-A")}
if ! {_git("diff", "--cached", "--quiet")}; then
  {_git("commit", "-q", "--no-verify", "-m", message)}
fi
git rev-parse HEAD
"""
        done = await self.exec(script)
        if done.code != 0:
            raise SandboxError(f"commit failed: {done.output}")
        head = done.output.splitlines()[-1]
        if not SHA.match(head):
            raise SandboxError(f"unexpected HEAD: {head!r}")
        return None if head == _check_sha(base) else head

    async def diff_stat(self, base: str, sha: str) -> dict[str, int]:
        script = _git("-C", "/genome", "diff", "--shortstat", _check_sha(base), _check_sha(sha))
        done = await self.exec(script)
        numbers = [int(n) for n in re.findall(r"(\d+) ", done.output)]
        keys = ("files", "insertions", "deletions")
        return dict(zip(keys, numbers + [0] * (3 - len(numbers)), strict=False))
