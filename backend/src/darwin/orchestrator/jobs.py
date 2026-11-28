"""Long CPU-only jobs started by the agent (`run_job`): self-play, training.

A job runs on a snapshot of the working tree, in its own container without network, with
a CPU, time and disk ceiling. Its output stays under the data dir and is readable by later
sessions at /jobs/<id>/out; the agent deletes old outputs itself to stay under the quota.
"""

import asyncio
import logging
import os
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import sandbox
from darwin.referee import docker

log = logging.getLogger(__name__)

MAX_CPUS = 2.0
MAX_RUNNING = 1
LOG_TAIL_LINES = 40
DISK_CHECK_EVERY_S = 30.0
GB = 1024**3


def usage_bytes(path: Path) -> int:
    """Bytes under `path`, links not followed (the files are written by agent code)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except FileNotFoundError:
                continue  # removed while we walk
    return total


class JobError(Exception):
    pass


class Jobs:
    def __init__(
        self, settings: Settings, ledger: Ledger, on_done: Callable[[int], Awaitable[None]]
    ) -> None:
        self.settings = settings
        self.ledger = ledger
        self.on_done = on_done
        self._watchers: set[asyncio.Task[None]] = set()

    @property
    def root(self) -> Path:
        return self.settings.data_dir / "jobs"

    async def storage(self) -> tuple[float, float]:
        """GB used by all job outputs, and the ceiling."""
        used = await asyncio.to_thread(usage_bytes, self.root)
        return used / GB, self.settings.jobs_disk_gb

    async def delete(self, job_id: int) -> float:
        """Removes a finished job's files; returns the GB freed."""
        if any(job.id == job_id for job in await self.ledger.jobs(running_only=True)):
            raise JobError(f"job {job_id} is still running")
        target = self.root / str(int(job_id))
        if not target.is_dir():
            raise JobError(f"job {job_id} has no files")
        freed = await asyncio.to_thread(usage_bytes, target)
        await asyncio.to_thread(shutil.rmtree, target)
        return freed / GB

    async def start(self, experiment_id: int, command: str, hours: float) -> int:
        if len(await self.ledger.jobs(running_only=True)) >= MAX_RUNNING:
            raise JobError(f"at most {MAX_RUNNING} job at a time: wait for the running one")
        used, ceiling = await self.storage()
        if used >= ceiling:
            raise JobError(
                f"job storage is full ({used:.1f} of {ceiling:g} GB): delete old "
                "outputs with run_job action delete"
            )
        job_id = await self.ledger.start_job(experiment_id, command, MAX_CPUS, hours)
        snapshot = await sandbox.helper(
            self.settings,
            f"""
mkdir -p /jobs/{job_id}/src /jobs/{job_id}/out
tar -C /genome --exclude=./target -cf - . | tar -C /jobs/{job_id}/src -xf -
ln -s /tmp/target /jobs/{job_id}/src/target
""",
            extra_mounts=[(self.settings.data_dir / "jobs", "/jobs")],
        )
        if snapshot.code != 0:
            await self.ledger.finish_job(job_id, "failed", None, snapshot.output[-2000:])
            raise JobError(f"could not snapshot the working tree: {snapshot.output[-300:]}")
        run_id = docker.new_run_id()
        base = self.settings.data_dir / "jobs" / str(job_id)
        argv = [
            self.settings.docker_bin,
            "run",
            "-d",
            "--name",
            f"darwin-job-{job_id}",
            "--init",
            "--network",
            "none",
            "--cpus",
            str(MAX_CPUS),
            "--memory",
            "4g",
            "--pids-limit",
            "512",
            "--read-only",
            "--tmpfs",
            "/tmp:exec,size=4g",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "1000:1000",
            "-e",
            "HOME=/tmp",
            "-e",
            "CARGO_HOME=/tmp/cargo",
            # Builds stay in memory, outside the quota; the `target` link in the snapshot keeps
            # the contract's path, target/release/genome, working in a job too.
            "-e",
            "CARGO_TARGET_DIR=/tmp/target",
            "-e",
            f"OMP_NUM_THREADS={int(MAX_CPUS)}",  # PyTorch and rayon see every core otherwise
            "-e",
            f"RAYON_NUM_THREADS={int(MAX_CPUS)}",
            *docker.labels(self.settings, run_id),
            "-v",
            f"{base / 'src'}:/job/src",
            "-v",
            f"{base / 'out'}:/job/out",
            "-w",
            "/job/src",
            self.settings.lab_image,
            "bash",
            "-c",
            command,
        ]
        started = await docker.run(argv, 120)
        if started.returncode != 0:
            await self.ledger.finish_job(job_id, "failed", None, started.stderr[-2000:])
            raise JobError(f"job did not start: {started.stderr.strip()[-300:]}")
        task = asyncio.create_task(self._watch(job_id, run_id, hours, base / "out"))
        self._watchers.add(task)
        task.add_done_callback(self._watchers.discard)
        return job_id

    async def _watch(self, job_id: int, run_id: str, hours: float, out: Path) -> None:
        name = f"darwin-job-{job_id}"
        docker_bin = self.settings.docker_bin
        limit = self.settings.job_disk_gb * GB
        try:
            waiting = asyncio.create_task(docker.run([docker_bin, "wait", name], hours * 3600))
            killed_for = None
            while not waiting.done():
                await asyncio.wait({waiting}, timeout=DISK_CHECK_EVERY_S)
                if not waiting.done() and await asyncio.to_thread(usage_bytes, out) > limit:
                    killed_for = f"disk quota: output over {self.settings.job_disk_gb:g} GB"
                    await docker.run([docker_bin, "kill", name], 60)
            waited = waiting.result()
            logs = await docker.run([docker_bin, "logs", "--tail", str(LOG_TAIL_LINES), name], 60)
            tail = (logs.stdout + logs.stderr)[-4000:]
            if killed_for is not None:
                await self.ledger.finish_job(job_id, "killed", None, f"{killed_for}\n{tail}")
            elif waited.timed_out:
                await self.ledger.finish_job(job_id, "killed", None, f"time limit\n{tail}")
            else:
                code = int(waited.stdout.strip() or -1)
                await self.ledger.finish_job(job_id, "done" if code == 0 else "failed", code, tail)
        except Exception as exc:
            log.exception("job %s watcher failed", job_id)
            await self.ledger.finish_job(job_id, "failed", None, f"watcher error: {exc}")
        finally:
            await docker.remove_run_containers(self.settings, run_id)
        await self.on_done(job_id)

    async def recover(self) -> None:
        """Jobs left running by a previous process: their containers are gone or orphaned."""
        for job in await self.ledger.jobs(running_only=True):
            await docker.run([self.settings.docker_bin, "rm", "-f", f"darwin-job-{job.id}"], 60)
            await self.ledger.finish_job(job.id, "killed", None, "orchestrator restarted")
