"""Jobs in real containers: the build path, the disk quota, deleting outputs, the thread
limits."""

import asyncio
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.ledger.store import Ledger
from darwin.orchestrator import jobs as jobs_module
from darwin.orchestrator.jobs import JobError, Jobs
from darwin.referee.judge import Phase

pytestmark = pytest.mark.docker


async def started_experiment(ledger: Ledger) -> int:
    await ledger.seed("0" * 40)
    return await ledger.start_experiment(
        kind="iteration",
        phase=Phase.GENESIS,
        base_commit="0" * 40,
        base_generation_id=0,
        trigger="test",
    )


def settings_for(tmp_path: Path, job_disk_gb: float = 10.0, jobs_disk_gb: float = 40.0) -> Settings:
    genome = tmp_path / "genome"
    (genome / "src").mkdir(parents=True)
    (genome / "src" / "main.rs").write_text("fn main() {}\n")
    (genome / "Cargo.toml").write_text(
        '[package]\nname = "genome"\nversion = "0.1.0"\nedition = "2021"\n'
    )
    return Settings(
        data_dir=tmp_path / "data",
        genome_dir=genome,
        mirror_dir=tmp_path / "mirror.git",
        job_disk_gb=job_disk_gb,
        jobs_disk_gb=jobs_disk_gb,
    )


async def run_to_end(jobs: Jobs, experiment: int, command: str) -> int:
    finished = asyncio.Event()

    async def done(_job_id: int) -> None:
        finished.set()

    jobs.on_done = done
    job_id = await jobs.start(experiment, command, "A test job", hours=0.05)
    await asyncio.wait_for(finished.wait(), 120)
    return job_id


async def test_a_job_finds_the_binary_where_the_contract_puts_it(
    tmp_path: Path, ledger: Ledger, images: None
) -> None:
    settings = settings_for(tmp_path)
    jobs = Jobs(settings, ledger, on_done=ignore)
    job_id = await run_to_end(
        jobs,
        await started_experiment(ledger),
        "cargo build --release -q && test -x target/release/genome && touch /job/out/built",
    )
    [job] = await ledger.jobs()
    assert job.status == "done", job.log_tail
    assert (settings.data_dir / "jobs" / str(job_id) / "out" / "built").exists()
    # The build itself stays in the container's memory: in the job's files only the link.
    assert (settings.data_dir / "jobs" / str(job_id) / "src" / "target").is_symlink()


async def test_a_job_writing_past_its_quota_is_killed(
    tmp_path: Path, ledger: Ledger, images: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs_module, "DISK_CHECK_EVERY_S", 0.5)
    settings = settings_for(tmp_path, job_disk_gb=0.001)  # about 1 MB
    jobs = Jobs(settings, ledger, on_done=ignore)
    job_id = await run_to_end(
        jobs, await started_experiment(ledger), "head -c 3000000 /dev/zero > /job/out/big; sleep 60"
    )
    [job] = await ledger.jobs()
    assert (job.id, job.status) == (job_id, "killed")
    assert job.log_tail and job.log_tail.startswith("disk quota")


async def test_outputs_count_against_storage_and_can_be_deleted(
    tmp_path: Path, ledger: Ledger, images: None
) -> None:
    settings = settings_for(tmp_path)
    jobs = Jobs(settings, ledger, on_done=ignore)
    job_id = await run_to_end(
        jobs,
        await started_experiment(ledger),
        "echo $OMP_NUM_THREADS $RAYON_NUM_THREADS > /job/out/threads; "
        "python -c 'import torch; print(torch.get_num_threads())' >> /job/out/threads; "
        "head -c 2000000 /dev/zero > /job/out/data",
    )
    out = settings.data_dir / "jobs" / str(job_id) / "out"
    assert (out / "threads").read_text().split() == ["2", "2", "2"]
    used, _ = await jobs.storage()
    assert used > 0.0018
    assert await jobs.delete(job_id) > 0.0018
    assert not out.exists()
    with pytest.raises(JobError):
        await jobs.delete(job_id)


async def test_a_full_storage_refuses_new_jobs(tmp_path: Path, ledger: Ledger) -> None:
    settings = settings_for(tmp_path, jobs_disk_gb=0.000001)
    (settings.data_dir / "jobs" / "1" / "out").mkdir(parents=True)
    (settings.data_dir / "jobs" / "1" / "out" / "old").write_bytes(b"x" * 10_000)
    jobs = Jobs(settings, ledger, on_done=ignore)
    with pytest.raises(JobError, match="storage is full"):
        await jobs.start(await started_experiment(ledger), "true", "A test job", hours=0.1)


async def ignore(_job_id: int) -> None:
    return None
