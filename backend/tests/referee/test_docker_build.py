"""Build gate and judge on a real genome repository, compiled offline in the sandbox image."""

import subprocess
from pathlib import Path

import pytest

from darwin.config import Settings
from darwin.referee.build import build_gate
from darwin.referee.errors import RefereeError
from darwin.referee.judge import Phase, judge
from darwin.referee.models import Gate

pytestmark = pytest.mark.docker

CARGO_TOML = '[package]\nname = "genome"\nversion = "0.1.0"\nedition = "2021"\n'
MAIN_OK = 'fn main() {\n    println!("id name genome");\n}\n'
MAIN_BROKEN = 'fn main() {\n    let x: u32 = "not a number";\n}\n'


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True)  # fmt: skip
    return done.stdout.strip()


def commit(repo: Path, main_rs: str) -> str:
    """Commits in the genome and archives it in the mirror, as the orchestrator does."""
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "Cargo.toml").write_text(CARGO_TOML)
    (repo / "src" / "main.rs").write_text(main_rs)
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "step")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "push", "-q", str(repo.parent / "mirror.git"), f"HEAD:refs/darwin/exp-{sha[:8]}")
    return sha


@pytest.fixture
def genome(settings: Settings) -> Path:
    settings.genome_dir.mkdir(parents=True)
    git(settings.genome_dir, "init", "-q")
    subprocess.run(["git", "init", "-q", "--bare", str(settings.mirror_dir)], check=True)
    return settings.genome_dir


async def test_build_compiles_the_commit_and_caches_it(settings: Settings, genome: Path) -> None:
    sha = commit(genome, MAIN_OK)
    commit(genome, MAIN_BROKEN)  # the working tree moves on; the old commit still builds
    result, binary = await build_gate(settings, sha)
    assert result.passed, result.detail
    assert binary is not None and binary.path.is_file()
    again, _ = await build_gate(settings, sha)
    assert again.detail == {"cached": True}


async def test_build_failure_returns_the_compiler_output(settings: Settings, genome: Path) -> None:
    result, binary = await build_gate(settings, commit(genome, MAIN_BROKEN))
    assert not result.passed and binary is None
    assert result.detail["problem"] == "build_failed"
    assert "mismatched types" in result.detail["log"]


async def test_build_rejects_anything_but_a_full_sha(settings: Settings) -> None:
    with pytest.raises(RefereeError):
        await build_gate(settings, "HEAD; rm -rf /")


async def test_judge_stops_at_the_first_failed_gate(settings: Settings, genome: Path) -> None:
    verdict = await judge(settings, commit(genome, MAIN_BROKEN), Phase.FIRST_STEPS,
                          champion=None, seed=1)  # fmt: skip
    assert not verdict.accepted
    assert [gate.gate for gate in verdict.gates] == [Gate.BUILD]


async def test_judge_runs_perft_on_what_it_built(settings: Settings, genome: Path) -> None:
    verdict = await judge(settings, commit(genome, MAIN_OK), Phase.GENESIS, champion=None, seed=1)
    assert not verdict.accepted  # it builds, but it is not a UCI engine
    assert [gate.gate for gate in verdict.gates] == [Gate.BUILD, Gate.PERFT]
    assert verdict.gates[1].detail["problem"] == "protocol"
