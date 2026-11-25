"""History, code, memory and lab endpoints, against a real ledger and a real bare mirror."""

import asyncio
import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from darwin.api.app import app
from darwin.api.mind import MAX_MEMORY_BYTES
from darwin.config import get_settings
from darwin.ledger import commentary, lichess
from darwin.ledger.store import Ledger
from darwin.orchestrator.prompts import SYSTEM
from darwin.referee.judge import Phase, Verdict
from darwin.referee.match import MatchResult
from darwin.referee.models import GameRecord, Gate, GateResult, Termination
from darwin.referee.sprt import SprtVerdict

BIG_TEXT = "aé\n" * 100_000  # 400 KB, multibyte characters across the 256 KB cut
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


@dataclass
class Lab:
    gen0: str
    gen1: str
    data_dir: Path
    outside: Path


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, **GIT_ENV}
    done = subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)
    return done.stdout.decode().strip()


def build_mirror(tmp_path: Path) -> tuple[str, str, Path]:
    work, mirror = tmp_path / "work", tmp_path / "mirror.git"
    work.mkdir()
    git(tmp_path, "init", "-q", "--bare", str(mirror))
    git(work, "init", "-q")
    (work / ".gitignore").write_text("target/\n")
    (work / "README.md").write_text("one\ntwo\n")
    (work / "old.txt").write_text("".join(f"line {n}\n" for n in range(20)))
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "gen-0")
    gen0 = git(work, "rev-parse", "HEAD")
    (work / "README.md").write_text("one\nthree\nfour\n")
    (work / "src").mkdir()
    (work / "src" / "main.rs").write_text("fn main() {}\n")
    (work / "data.bin").write_bytes(b"\x00\x01binary" * 10)
    (work / "big.txt").write_text(BIG_TEXT)
    (work / "link").symlink_to("/etc/passwd")
    (work / "target" / "debug").mkdir(parents=True)
    (work / "target" / "debug" / "genome").write_text("build output\n")
    git(work, "mv", "old.txt", "new.txt")
    git(work, "add", "-A")
    git(work, "add", "-f", "target/debug/genome")
    git(work, "commit", "-q", "-m", "gen-1")
    gen1 = git(work, "rev-parse", "HEAD")
    for ref, sha in (("gen-0", gen0), ("gen-1", gen1), ("exp-1", gen1)):
        git(work, "push", "-q", str(mirror), f"{sha}:refs/darwin/{ref}")
    return gen0, gen1, mirror


def won_match() -> MatchResult:
    games = [GameRecord("candidate", "random", "1-0", Termination.CHECKMATE, "fen", "pgn")]
    return MatchResult(games, [0, 0, 0, 1, 0], 191.0, 80.0, 3.1, SprtVerdict.H1, "random", "2+0")


def seed_ledger(ledger_url: str, gen0: str, gen1: str) -> None:
    async def go() -> None:
        ledger = Ledger(ledger_url)
        await ledger.seed(gen0)
        first = await ledger.start_experiment(kind="iteration", phase=Phase.FIRST_STEPS,
                                              base_commit=gen0, base_generation_id=0,
                                              trigger="start")  # fmt: skip
        await ledger.set_submission(first, "Add a search", gen1, {"files": 4})
        gate = GateResult(Gate.MATCH, True, {"games": 1, "pgn": "1. e4"}, 5)
        await ledger.record_verdict(first, Verdict(True, [gate], None, won_match()))
        await ledger.set_lesson(first, "Search pays.")
        for cost in (0.1, 0.2):
            await ledger.add_llm_call(first, "m", input_tokens=100, cached_tokens=50,
                                      output_tokens=10, cost_usd=cost)  # fmt: skip
        reflection = await ledger.start_experiment(kind="reflection", phase=Phase.EVOLUTION,
                                                   base_commit=gen1, base_generation_id=1,
                                                   trigger="every")  # fmt: skip
        await ledger.add_llm_call(reflection, "m", input_tokens=1, cached_tokens=0,
                                  output_tokens=1, cost_usd=0.05)  # fmt: skip
        await ledger.finish_experiment(reflection, "done")
        third = await ledger.start_experiment(kind="iteration", phase=Phase.EVOLUTION,
                                              base_commit=gen1, base_generation_id=1,
                                              trigger="verdict")  # fmt: skip
        await ledger.set_submission(third, "Tweak eval", "f" * 40, {"files": 1})
        failed = GateResult(Gate.PERFT, False, {"problem": "wrong_count"}, 9)
        await ledger.record_verdict(third, Verdict(False, [failed], None, None))
        await ledger.add_rating(0, "anchors_below", 1320.0, None, {})
        await ledger.add_rating(1, "anchors", 1500.0, 40.0, {})
        await commentary.add(ledger, commentary.Subject(commentary.TITLE, first),
                             text_it="Una ricerca", text_en="A search", model="m",
                             input_tokens=1, output_tokens=1, cost_usd=0.0)  # fmt: skip
        await lichess.start_game(ledger, lichess_id="g1", generation_id=1, color="white",
                                 opponent="bot", opponent_rating=1400, opponent_title="BOT",
                                 rated=True, time_control="180+2")  # fmt: skip
        await lichess.finish_game(ledger, "g1", status="mate", result="win", moves="e2e4",
                                  rating_after=1510)  # fmt: skip
        await ledger.close()

    asyncio.run(go())


@pytest.fixture
def lab(ledger_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lab:
    gen0, gen1, mirror = build_mirror(tmp_path)
    seed_ledger(ledger_url, gen0, gen1)
    data_dir = tmp_path / "data"
    memory = data_dir / "agent" / "memory"
    memory.mkdir(parents=True)
    (memory / "STRATEGY.md").write_text("Search first.\n")
    outside = tmp_path / "secret.txt"
    outside.write_text("host secret\n")
    (memory / "NOTES.md").symlink_to(outside)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n")
    monkeypatch.setenv("DARWIN_MIRROR_DIR", str(mirror))
    monkeypatch.setenv("DARWIN_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DARWIN_CHANGELOG_PATH", str(changelog))
    changelog_en = tmp_path / "CHANGELOG.en.md"
    changelog_en.write_text("# Changelog (en)\n")
    monkeypatch.setenv("DARWIN_CHANGELOG_EN_PATH", str(changelog_en))
    return Lab(gen0, gen1, data_dir, outside)


@pytest.fixture
def client(lab: Lab, ledger_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DARWIN_LEDGER_URL", ledger_url)
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_tree_defaults_to_the_champion_and_hides_build_output(client: TestClient, lab: Lab) -> None:
    body = client.get("/api/code/tree").json()
    assert (body["ref"], body["commit"], body["generation"]) == ("gen-1", lab.gen1, 1)
    paths = [f["path"] for f in body["files"]]
    assert paths == [".gitignore", "README.md", "big.txt", "data.bin", "link", "new.txt",
                     "src/main.rs"]  # fmt: skip
    assert {"path": "src/main.rs", "size": 13} in body["files"]

    by_sha = client.get("/api/code/tree", params={"ref": lab.gen0}).json()
    assert (by_sha["generation"], by_sha["commit"]) == (0, lab.gen0)
    assert "old.txt" in [f["path"] for f in by_sha["files"]]


def test_file_reads_text_binary_links_and_truncates(client: TestClient, lab: Lab) -> None:
    def get(path: str, ref: str = "gen-1") -> dict[str, object]:
        response = client.get("/api/code/file", params={"ref": ref, "path": path})
        assert response.status_code == 200, response.text
        body: dict[str, object] = response.json()
        return body

    text = get("src/main.rs")
    assert text["content"] == "fn main() {}\n"
    assert (text["binary"], text["truncated"], text["commit"]) == (False, False, lab.gen1)
    binary = get("data.bin")
    assert (binary["binary"], binary["content"]) == (True, None)
    big = get("big.txt", ref="exp-1")
    assert (big["binary"], big["truncated"], big["size"]) == (False, True, 400_000)
    assert isinstance(big["content"], str) and BIG_TEXT.startswith(big["content"])
    assert len(big["content"].encode()) > 256 * 1024 - 4
    # A link is data: its target as text, never the file it points to.
    assert get("link")["content"] == "/etc/passwd"


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"ref": "HEAD", "path": "README.md"}, 400),
        ({"ref": "gen-1; rm -rf /", "path": "README.md"}, 400),
        ({"ref": "gen-9", "path": "README.md"}, 404),
        ({"ref": "e" * 40, "path": "README.md"}, 404),
        ({"ref": "gen-1", "path": "../README.md"}, 400),
        ({"ref": "gen-1", "path": "/etc/passwd"}, 400),
        ({"ref": "gen-1", "path": "src/../README.md"}, 400),
        ({"ref": "gen-1", "path": "missing.txt"}, 404),
        ({"ref": "gen-1", "path": "src"}, 404),
        ({"ref": "gen-1", "path": "target/debug/genome"}, 404),
        ({"ref": "gen-1"}, 400),
    ],
)
def test_bad_refs_and_paths_are_refused(
    client: TestClient, params: dict[str, str], status: int
) -> None:
    assert client.get("/api/code/file", params=params).status_code == status


def test_diff_of_a_generation(client: TestClient, lab: Lab) -> None:
    body = client.get("/api/code/diff", params={"gen": 1}).json()
    assert (body["from"], body["to"]) == (lab.gen0, lab.gen1)
    files = {f["path"]: f for f in body["files"]}
    assert not any(path.startswith("target/") for path in files)
    readme = files["README.md"]
    assert (readme["status"], readme["additions"], readme["deletions"]) == ("modified", 2, 1)
    assert "+three" in readme["patch"] and "-two" in readme["patch"]
    assert files["src/main.rs"]["status"] == "added"
    assert files["new.txt"]["status"] == "renamed"
    assert (files["data.bin"]["patch"], files["data.bin"]["additions"]) == ("", 0)
    big = files["big.txt"]["patch"]
    assert big.endswith("... (truncated)") and len(big.encode()) <= 64 * 1024 + 20

    by_exp = client.get("/api/code/diff", params={"exp": 1}).json()
    assert by_exp == body
    by_refs = client.get("/api/code/diff", params={"from": "gen-0", "to": lab.gen1}).json()
    assert by_refs == body


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"gen": "1", "exp": "1"}, 400),
        ({"from": "gen-0"}, 400),
        ({}, 400),
        ({"gen": "0"}, 400),
        ({"gen": "x"}, 400),
        ({"gen": "5"}, 404),
        ({"exp": "3"}, 404),  # its candidate never reached the mirror
        ({"exp": "99"}, 404),
    ],
)
def test_bad_diff_requests(client: TestClient, params: dict[str, str], status: int) -> None:
    assert client.get("/api/code/diff", params=params).status_code == status


def test_mind_refuses_a_linked_memory_file(client: TestClient, lab: Lab) -> None:
    body = client.get("/api/mind").json()
    assert body["strategy"] == "Search first.\n"
    assert body["notes"] == ""  # NOTES.md links outside the memory folder
    assert body["system_prompt"] == SYSTEM
    assert body["updated_at"] is not None

    notes = lab.data_dir / "agent" / "memory" / "NOTES.md"
    notes.unlink()
    notes.write_text("old line\n" * 20_000 + "newest line\n")
    tail = client.get("/api/mind").json()["notes"]
    assert tail.endswith("newest line\n") and len(tail.encode()) <= MAX_MEMORY_BYTES


def test_generations_detail_newest_first(client: TestClient, lab: Lab) -> None:
    gen1, gen0 = client.get("/api/generations/detail").json()
    assert gen1["id"] == 1 and gen1["parent_commit"] == lab.gen0
    assert (gen1["elo_absolute"], gen1["below_ladder"], gen1["tried"]) == (1500.0, False, 1)
    assert gen1["elo_absolute_error"] == 40.0
    assert gen1["title"] == {"it": "Una ricerca", "en": "A search"}
    assert (gen1["hypothesis"], gen1["lesson"], gen1["experiment_id"]) == (
        "Add a search", "Search pays.", 1)  # fmt: skip
    assert gen1["diff_stat"] == {"files": 4}
    assert gen1["lichess"] == {"games": 1, "wins": 1, "draws": 0, "losses": 0,
                               "performance": 1800}  # fmt: skip
    assert (gen0["parent_commit"], gen0["below_ladder"], gen0["elo_absolute"]) == (
        None, True, None)  # fmt: skip
    assert (gen0["elo_absolute_error"], gen0["title"]) == (None, None)
    assert gen0["lichess"] is None


def test_experiments_page_through_every_kind(client: TestClient) -> None:
    first = client.get("/api/experiments", params={"limit": 2}).json()
    assert [e["id"] for e in first["items"]] == [3, 2]
    assert first["next_before_id"] == 2
    assert first["items"][0]["gates"] == [
        {"gate": "perft", "passed": False, "detail": {"problem": "wrong_count"}}
    ]
    assert first["items"][1]["kind"] == "reflection"
    rest = client.get("/api/experiments", params={"limit": 2, "before_id": 2}).json()
    assert rest["next_before_id"] is None
    (exp,) = rest["items"]
    assert exp["cost_usd"] == pytest.approx(0.3)
    assert exp["gates"] == [{"gate": "match", "passed": True, "detail": {"games": 1}}]
    assert (exp["match"]["verdict"], exp["match"]["wins"]) == ("h1", 1)
    assert exp["title"] == {"it": "Una ricerca", "en": "A search"}
    assert first["items"][0]["title"] is None  # not written yet
    assert first["counts"] == {"total": 3, "accepted": 1, "rejected": 1, "done": 1}
    for bad in ({"limit": 0}, {"limit": 101}, {"before_id": "x"}, {"status": "Rejected;"}):
        assert client.get("/api/experiments", params=bad).status_code == 400


def test_experiments_filtered_by_status_keep_the_counts_of_all(client: TestClient) -> None:
    body = client.get("/api/experiments", params={"status": "rejected,error"}).json()
    assert [e["id"] for e in body["items"]] == [3]
    assert body["counts"]["total"] == 3
    none = client.get("/api/experiments", params={"status": "stale"}).json()
    assert (none["items"], none["next_before_id"]) == ([], None)


def test_lab_totals(client: TestClient) -> None:
    body = client.get("/api/lab").json()
    assert body["started_at"] is not None
    assert body["totals"] == {
        "spend_usd": pytest.approx(0.35),
        "sessions": 3,
        "iterations": 2,
        "accepted": 1,
        "rejected": 1,
        "llm_calls": 3,
        "input_tokens": 201,
        "cached_tokens": 100,
        "output_tokens": 21,
        "lichess_games": 1,
    }
    assert body["cost_per_generation"] == [{"generation": 1, "usd": pytest.approx(0.3)}]
    assert body["changelog"] == "# Changelog\n"
    assert body["changelog_en"] == "# Changelog (en)\n"
