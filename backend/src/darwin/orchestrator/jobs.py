"""Long CPU-only jobs started by the agent (`run_job`): self-play, training.

A job runs on a snapshot of the working tree, in its own container without network, with
a CPU and time ceiling. Its output stays under the data dir and is readable by later
sessions at /jobs/<id>/out.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import sandbox
from darwin.referee import docker

log = logging.getLogger(__name__)

MAX_CPUS = 2.0
MAX_RUNNING = 1
LOG_TAIL_LINES = 40


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

    async def start(self, experiment_id: int, command: str, hours: float) -> int:
        if len(await self.ledger.jobs(running_only=True)) >= MAX_RUNNING:
            raise JobError(f"at most {MAX_RUNNING} job at a time: wait for the running one")
        job_id = await self.ledger.start_job(experiment_id, command, MAX_CPUS, hours)
        snapshot = await sandbox.helper(
            self.settings,
            f"""
mkdir -p /jobs/{job_id}/src /jobs/{job_id}/out
tar -C /genome --exclude=./target -cf - . | tar -C /jobs/{job_id}/src -xf -
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
            "-e",
            "CARGO_TARGET_DIR=/tmp/target",
            "--label",
            f"{docker.RUN_LABEL}={run_id}",
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
        task = asyncio.create_task(self._watch(job_id, run_id, hours))
        self._watchers.add(task)
        task.add_done_callback(self._watchers.discard)
        return job_id

    async def _watch(self, job_id: int, run_id: str, hours: float) -> None:
        name = f"darwin-job-{job_id}"
        docker_bin = self.settings.docker_bin
        try:
            waited = await docker.run([docker_bin, "wait", name], hours * 3600)
            logs = await docker.run([docker_bin, "logs", "--tail", str(LOG_TAIL_LINES), name], 60)
            tail = (logs.stdout + logs.stderr)[-4000:]
            if waited.timed_out:
                await self.ledger.finish_job(job_id, "killed", None, tail)
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
