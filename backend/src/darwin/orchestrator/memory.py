"""The history of the agent's memory folder (`NOTES.md`, `STRATEGY.md` and whatever else the
agent keeps there): a commit after every session in `data/agent/memory.git`, a bare
repository only the orchestrator writes. The folder itself is overwritten in place, so
without it every version but the last is lost.

The folder belongs to the agent, so git never runs on it from the host: the commit is made
in a one-shot container that mounts it read-only, as for the genome (`sandbox.helper`).
"""

import logging
import shlex
from datetime import datetime
from pathlib import Path

from darwin.config import Settings
from darwin.orchestrator.sandbox import SHA, SandboxError, helper

log = logging.getLogger(__name__)

BRANCH = "refs/heads/main"
NO_COMMIT = "0" * 40
IDENTITY = ["-c", "user.name=darwin-orchestrator", "-c", "user.email=orchestrator@darwin.local",
            "-c", "safe.directory=*"]  # fmt: skip


def memory_dir(settings: Settings) -> Path:
    return settings.data_dir / "agent" / "memory"


def history_dir(settings: Settings) -> Path:
    return settings.data_dir / "agent" / "memory.git"


def commit_script(message: str, date: datetime | None = None) -> str:
    """The shell that commits /memory on top of /history's branch, printing the new commit
    or `unchanged`. `--force` records what a `.gitignore` of the agent's would hide; Python
    bytecode caches are left out. The ref moves only from the parent it was built on."""
    git = shlex.join(["git", *IDENTITY])
    when = ""
    if date is not None:
        stamp = shlex.quote(date.isoformat())
        when = f"export GIT_AUTHOR_DATE={stamp} GIT_COMMITTER_DATE={stamp}"
    return f"""
test -f /history/HEAD || git init -q --bare /history
export GIT_DIR=/history GIT_WORK_TREE=/memory GIT_INDEX_FILE=/tmp/index
{when}
cd /memory
{git} add --all --force -- . ':(exclude,glob)**/__pycache__/**'
tree=$({git} write-tree)
parent=$({git} rev-parse -q --verify {BRANCH} || true)
if [ -n "$parent" ] && [ "$({git} rev-parse "$parent^{{tree}}")" = "$tree" ]; then
  echo unchanged
  exit 0
fi
commit=$({git} commit-tree "$tree" ${{parent:+-p "$parent"}} -m {shlex.quote(message)})
{git} update-ref {BRANCH} "$commit" "${{parent:-{NO_COMMIT}}}"
echo "$commit"
"""


async def snapshot(
    settings: Settings,
    message: str,
    *,
    source: Path | None = None,
    date: datetime | None = None,
) -> str | None:
    """Commits the memory folder (or `source`) as it is now; the new commit, or None when
    nothing changed since the last one."""
    folder = source or memory_dir(settings)
    history = history_dir(settings)
    history.mkdir(parents=True, exist_ok=True)
    done = await helper(
        settings,
        commit_script(message, date),
        extra_mounts=[(folder, "/memory:ro"), (history, "/history")],
        timeout_s=120,
    )
    last = done.output.splitlines()[-1] if done.output else ""
    if done.code != 0:
        raise SandboxError(f"cannot commit the memory: {done.output}")
    if last == "unchanged":
        return None
    if not SHA.match(last):
        raise SandboxError(f"unexpected answer from the memory commit: {done.output}")
    return last


async def keep(settings: Settings, message: str) -> None:
    """`snapshot` that never fails its caller: a lost version is logged, not fatal."""
    try:
        sha = await snapshot(settings, message)
    except Exception:
        log.exception("could not commit the agent's memory (%s)", message)
        return
    if sha is not None:
        log.info("memory committed: %s (%s)", sha[:10], message)
