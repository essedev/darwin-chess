"""The agent's memory files and the platform changelog, read for the dashboard.

The memory folder is written by the agent (mounted as /memory in its sandbox): a file there
may be a link to anywhere, or a FIFO. A file is read only when its resolved path stays in the
folder, it is opened without following a final link and it is a regular file; reads are capped.
"""

import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_MEMORY_BYTES = 64 * 1024
MAX_CHANGELOG_BYTES = 256 * 1024


def _read_capped(path: Path, folder: Path, *, tail: bool) -> tuple[str, float] | None:
    """The file's text (its start, or its end when `tail`) and mtime, or None if refused."""
    try:
        root = folder.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if resolved.parent != root:
        return None
    try:
        fd = os.open(resolved, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            return None
        if tail and info.st_size > MAX_MEMORY_BYTES:
            handle.seek(info.st_size - MAX_MEMORY_BYTES)
        data = handle.read(MAX_MEMORY_BYTES)
    if tail and info.st_size > MAX_MEMORY_BYTES:
        data = data.lstrip(bytes(range(0x80, 0xC0)))  # a character cut at the start
    return data.decode("utf-8", errors="replace"), info.st_mtime


def read_mind(data_dir: Path, system_prompt: str) -> dict[str, Any]:
    memory = data_dir / "agent" / "memory"
    strategy = _read_capped(memory / "STRATEGY.md", memory, tail=False)
    notes = _read_capped(memory / "NOTES.md", memory, tail=True)
    mtimes = [found[1] for found in (strategy, notes) if found is not None]
    return {
        "strategy": strategy[0] if strategy else "",
        "notes": notes[0] if notes else "",
        "system_prompt": system_prompt,
        "updated_at": datetime.fromtimestamp(max(mtimes), UTC).isoformat() if mtimes else None,
    }


def read_changelog(path: Path) -> str:
    """The platform changelog (a trusted file shipped with the image), or "" without one."""
    try:
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return ""
            data = handle.read(MAX_CHANGELOG_BYTES)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")
