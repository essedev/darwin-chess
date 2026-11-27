"""Rebuilds the history of the agent's memory folder from before it was versioned (27 November
2026) and puts it under the live history in data/agent/memory.git.

Run once inside `core`, which has the ledger, the Docker CLI and the lab image:

    docker compose exec -T core python - < scripts/rebuild-memory-history.py

The agent changed its memory with tool calls, all in the ledger's `agent_events`. They are
replayed in order on a copy of the seed: `write` and `edit` here, `bash` commands that
touch the memory in a lab container like the sandbox (no network, git and cargo stubbed so
that a chain such as `git commit && echo ... >> /memory/NOTES.md` reaches the memory). The
commentary worker kept exact copies of NOTES.md and STRATEGY.md, at most one an hour, and
every file in the folder today is exact from its last modification on: each of these is
compared with the replay at its time and, when they differ, replaces it. The result
is one commit per session, dated at its last tool call, in a separate repository; then the
live commits are replayed on top of it and the branch moves only if nobody committed since.
"""

import ast
import json
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from darwin.config import Settings
from darwin.ledger.backup import ledger_file
from darwin.orchestrator import memory
from darwin.orchestrator.loop import SEED_MEMORY
from darwin.orchestrator.sandbox import helper
from darwin.referee import docker

MEMORY_FILES = ("NOTES.md", "STRATEGY.md")
# A command that may change the memory: a redirection, an in-place edit, a file written by
# a script. Reads (cat, head, grep) are not replayed.
MUTATES = re.compile(
    r">>?\s*\S*(NOTES|STRATEGY|memory/)|sed -i|open\([^)]*['\"]w['\"]|\.write\(|"
    r"(cp|mv)\s[^|;&]*memory|tee\s"
)
STUB = "#!/bin/sh\nexit 0\n"
LAB_PATH = "/shims:/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin"


@dataclass
class Report:
    replayed: int = 0
    failed_edits: list[int] = field(default_factory=list)
    cut_writes: list[int] = field(default_factory=list)
    checks: list[dict[str, object]] = field(default_factory=list)
    # Files whose replayed text is known to be wrong (a rewrite the ledger kept cut, an edit
    # that no longer applies) until a translator's copy sets them right again.
    uncertain: set[str] = field(default_factory=set)
    uncertain_commits: int = 0


def args_of(payload: dict[str, object]) -> tuple[dict[str, object], bool]:
    """The call's arguments and whether the ledger kept them whole."""
    raw = payload.get("args")
    if isinstance(raw, dict):
        return raw, not payload.get("cut")
    if isinstance(raw, str):  # rows before 2026-11-26: Python's repr, cut at 2,000 as a whole
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            path = re.search(r"'path': '(/memory/[^']+)'", raw)
            return ({"path": path.group(1)} if path else {}), False
        return (parsed if isinstance(parsed, dict) else {}), True
    return {}, True


def memory_name(path: object) -> str | None:
    text = str(path or "")
    if text.startswith("/memory/"):
        name = text.removeprefix("/memory/")
        return name if name and ".." not in name.split("/") else None
    return None


def files_now(folder: Path) -> dict[str, tuple[datetime, bytes]]:
    """Every regular file in the memory folder with its last modification. Links are left
    out: the folder is the agent's, and a link could point at anything in this container."""
    found: dict[str, tuple[datetime, bytes]] = {}
    for path in folder.rglob("*"):
        rel = path.relative_to(folder)
        if "__pycache__" in rel.parts or any(p.is_symlink() for p in (path, *path.parents)):
            continue
        if path.is_file():
            when = datetime.fromtimestamp(path.lstat().st_mtime, UTC)
            found[str(rel)] = (when, path.read_bytes())
    return found


def stamp(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def run_in_lab(settings: Settings, work: Path, genome: Path, shims: Path, command: str) -> None:
    run_id = docker.new_run_id()
    argv = [
        settings.docker_bin, "run", "--rm", "--network", "none", "--user", "1000:1000",
        "--read-only", "--tmpfs", "/tmp:exec,size=512m", "-e", "HOME=/tmp",
        "-e", f"PATH={LAB_PATH}",
        *docker.labels(settings, run_id),
        "-v", f"{work}:/memory", "-v", f"{genome}:/genome", "-v", f"{shims}:/shims:ro",
        "-w", "/genome", settings.lab_image, "timeout", "-s", "KILL", "60", "bash", "-c", command,
    ]  # fmt: skip
    try:
        subprocess.run(argv, capture_output=True, timeout=90, check=False)
    finally:
        subprocess.run(
            [settings.docker_bin, "rm", "-f", *container_ids(settings, run_id)],
            capture_output=True,
            check=False,
        )


def container_ids(settings: Settings, run_id: str) -> list[str]:
    done = subprocess.run(
        [settings.docker_bin, "ps", "-aq", "--filter", f"label=darwin.run={run_id}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.split() or ["none"]


def apply_edit(work: Path, name: str, edits: list[dict[str, str]]) -> bool:
    target = work / name
    text = target.read_text() if target.exists() else ""
    for edit in edits:
        old, new = edit.get("oldText", ""), edit.get("newText", "")
        if text.count(old) != 1:  # pi refuses an edit whose text is missing or ambiguous
            return False
        text = text.replace(old, new)
    target.write_text(text)
    return True


async def commit_rebuilt(settings: Settings, work: Path, history: Path, message: str,
                         date: datetime) -> None:  # fmt: skip
    done = await helper(
        settings,
        memory.commit_script(message, date),
        extra_mounts=[(work, "/memory:ro"), (history, "/history")],
        timeout_s=120,
    )
    if done.code != 0:
        raise SystemExit(f"commit failed: {done.output}")


def graft_script() -> str:
    """Fetches the rebuilt history and replays the live commits on top of it, keeping their
    trees, messages and dates; the branch moves only from the head it was read at."""
    git = shlex.join(["git", *memory.IDENTITY])
    return f"""
test -f /history/HEAD || git init -q --bare /history
export GIT_DIR=/history
{git} fetch -q /rebuilt +refs/heads/main:refs/rebuilt/main
live=$({git} rev-parse -q --verify {memory.BRANCH} || true)
top=$({git} rev-parse refs/rebuilt/main)
if [ -n "$live" ]; then
  for c in $({git} rev-list --reverse "$live"); do
    export GIT_AUTHOR_DATE="$({git} log -1 --format=%aI "$c")"
    export GIT_COMMITTER_DATE="$({git} log -1 --format=%cI "$c")"
    top=$({git} log -1 --format=%B "$c" | {git} commit-tree "$c^{{tree}}" -p "$top")
  done
fi
{git} update-ref {memory.BRANCH} "$top" "${{live:-{memory.NO_COMMIT}}}"
{git} update-ref -d refs/rebuilt/main
echo "$top"
"""


async def main() -> None:
    settings = Settings()
    root = settings.data_dir / "scratch" / "memory-rebuild"
    if root.exists():
        shutil.rmtree(root)
    work, genome, shims, history = (root / n for n in ("memory", "genome", "shims", "history.git"))
    for folder in (work, genome, shims, history):
        folder.mkdir(parents=True)
        folder.chmod(0o777)  # written by containers running as uid 1000
    for tool in ("git", "cargo"):
        (shims / tool).write_text(STUB)
        (shims / tool).chmod(0o755)
    for name in MEMORY_FILES:
        shutil.copy(SEED_MEMORY / name, work / name)
        (work / name).chmod(0o666)

    source = ledger_file(settings.ledger_url)
    assert source is not None
    db = sqlite3.connect(source)
    db.row_factory = sqlite3.Row
    events = db.execute(
        "select id, experiment_id, kind, payload, created_at from agent_events "
        "where kind = 'tool_call' order by id"
    ).fetchall()
    copies = db.execute(
        "select kind, text_en, created_at from commentaries "
        "where kind in ('notes', 'strategy') order by created_at"
    ).fetchall()
    sessions = {
        r["id"]: r["kind"] for r in db.execute("select id, kind from experiments").fetchall()
    }

    # One timeline: tool calls and the translator's copies, in time order.
    finals = files_now(memory.memory_dir(settings))
    timeline: list[tuple[datetime, str, object]] = [
        (stamp(e["created_at"]), "call", e) for e in events
    ] + [(stamp(c["created_at"]), "copy", c) for c in copies]
    timeline += [(when, "final", name) for name, (when, _) in finals.items()]
    timeline.sort(key=lambda item: item[0])

    report = Report()
    last_of: dict[int, datetime] = {}
    for e in events:
        last_of[e["experiment_id"]] = stamp(e["created_at"])
    done_sessions: set[int] = set()

    async def close_sessions_before(when: datetime) -> None:
        for exp_id, last in sorted(last_of.items(), key=lambda kv: kv[1]):
            if exp_id in done_sessions or last > when:
                continue
            done_sessions.add(exp_id)
            kind = sessions.get(exp_id, "iteration")
            checks = [c for c in report.checks if c["session"] == exp_id]
            note = "; ".join(f"{c['file']} against {c['against']}: {c['result']}" for c in checks)
            message = (
                f"exp-{exp_id}: after the {kind} session (rebuilt)\n\n"
                "Rebuilt on 27 November 2026 from the session's tool calls."
            )
            if note:
                message += f" Checked: {note}."
            if report.uncertain:
                report.uncertain_commits += 1
                files = ", ".join(sorted(report.uncertain))
                message += (
                    f"\n\nUncertain: {files}. A change to it was kept cut in the ledger, so "
                    "this text is not the one the agent had, until a later exact copy "
                    "sets it right."
                )
            await commit_rebuilt(settings, work, history, message, last)

    current_session = 0
    # Files past their last modification: a call logged a moment after the change it made
    # must not apply it twice.
    frozen: dict[str, bytes] = {}
    for when, what, row in timeline:
        await close_sessions_before(when)
        if what in {"copy", "final"}:
            if what == "copy":
                assert isinstance(row, sqlite3.Row)
                name = "NOTES.md" if row["kind"] == "notes" else "STRATEGY.md"
                exact, source_name = (row["text_en"] or "").encode(), "the translator's copy"
            else:
                name, exact, source_name = str(row), finals[str(row)][1], "today's file"
            target = work / name
            replayed = target.read_bytes() if target.exists() else b""
            same = replayed.strip() == exact.strip()
            report.checks.append({
                "file": name, "at": when.isoformat(), "session": current_session,
                "against": source_name,
                "result": "matched" if same else f"differed, replaced by {source_name}",
            })  # fmt: skip
            if not same:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(exact)
            report.uncertain.discard(name)
            if what == "final":
                frozen[name] = exact
            continue
        assert isinstance(row, sqlite3.Row)
        current_session = row["experiment_id"]
        payload = json.loads(row["payload"])
        tool = payload.get("tool")
        args, whole = args_of(payload)
        if tool in {"write", "edit"} and memory_name(args.get("path")) in frozen:
            continue
        if tool in {"write", "edit"} and (name := memory_name(args.get("path"))) and not whole:
            report.cut_writes.append(row["id"])
            report.uncertain.add(name)  # the old text stays: a cut one would be worse
        elif tool == "write" and (name := memory_name(args.get("path"))):
            (work / name).parent.mkdir(parents=True, exist_ok=True)
            (work / name).write_text(str(args.get("content", "")))
            report.uncertain.discard(name)
            report.replayed += 1
        elif tool == "edit" and (name := memory_name(args.get("path"))):
            edits = args.get("edits")
            if not isinstance(edits, list):
                edits = [{"oldText": args.get("oldText", ""), "newText": args.get("newText", "")}]
            if not apply_edit(work, name, edits):
                report.failed_edits.append(row["id"])
                report.uncertain.add(name)
            report.replayed += 1
        elif tool == "bash":
            command = str(args.get("command", ""))
            if re.search(r"memory|NOTES|STRATEGY", command) and MUTATES.search(command):
                run_in_lab(settings, work, genome, shims, command)
                for name, exact in frozen.items():
                    (work / name).write_bytes(exact)
                report.replayed += 1
    await close_sessions_before(datetime.max.replace(tzinfo=UTC))

    # The live history goes on top of the rebuilt one.
    memory.history_dir(settings).mkdir(parents=True, exist_ok=True)
    done = await helper(
        settings,
        graft_script(),
        extra_mounts=[(history, "/rebuilt:ro"), (memory.history_dir(settings), "/history")],
        timeout_s=300,
    )
    if done.code != 0:
        raise SystemExit(f"graft failed: {done.output}")

    matched = sum(c["result"] == "matched" for c in report.checks)
    json.dump(
        {
            "sessions": len(done_sessions),
            "replayed_changes": report.replayed,
            "failed_edits": report.failed_edits,
            "cut_writes": report.cut_writes,
            "uncertain_commits": report.uncertain_commits,
            "checks_matched": f"{matched}/{len(report.checks)}",
            "checks": report.checks,
            "head": done.output.splitlines()[-1],
        },
        sys.stdout,
        indent=1,
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
