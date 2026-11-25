"""Read-only access to the genome's code through the trusted bare mirror.

The mirror's refs and config belong to the orchestrator, but every file in it was written by
the agent: contents are returned as text and never executed, sizes are capped, refs and paths
are validated before they reach git, and git runs without a shell, with literal pathspecs, no
external diff or textconv drivers and no host configuration.
"""

import asyncio
import codecs
import contextlib
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

GIT_TIMEOUT_S = 10.0
MAX_TEXT_BYTES = 256 * 1024
MAX_PATCH_BYTES = 64 * 1024
MAX_LISTING_BYTES = 8 * 1024 * 1024
MAX_PATCHED_FILES = 200  # files past this one in a diff get a truncated patch
BINARY_SNIFF_BYTES = 8 * 1024
TRUNCATED = "... (truncated)"

_REF = re.compile(r"(gen|exp)-(\d{1,9})|[0-9a-f]{40}")
_STATUS = {"A": "added", "C": "added", "D": "deleted", "R": "renamed"}  # else "modified"


class BadRequest(ValueError):
    """A ref or path that is not acceptable at all (HTTP 400)."""


class NotFound(LookupError):
    """A well-formed ref or path that does not exist in the mirror (HTTP 404)."""


class GitError(RuntimeError):
    """git failed or timed out on a well-formed request."""


def check_path(path: str) -> str:
    segments = path.split("/")
    if (
        not path
        or len(path) > 1024
        or "\0" in path
        or path.startswith("/")
        or any(seg in {"", ".", ".."} for seg in segments)
    ):
        raise BadRequest(f"bad path {path!r}")
    return path


def hidden(path: str) -> bool:
    """Build output and git internals are not part of the code shown."""
    return path.startswith("target/") or ".git" in path.split("/")


def _git_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }


class Mirror:
    """git on the bare mirror: a few processes at a time, each with a timeout."""

    def __init__(self, git_dir: Path, *, concurrency: int = 4, cache_size: int = 32) -> None:
        self.git_dir = git_dir
        self._slots = asyncio.Semaphore(concurrency)
        self._diffs: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
        self._cache_size = cache_size

    async def _git(self, *args: str, limit: int = MAX_LISTING_BYTES) -> tuple[bytes, bool]:
        """stdout (at most `limit` bytes) and whether it was cut there."""
        cmd = ["git", "-c", "safe.directory=*", "--git-dir", str(self.git_dir)]
        cmd += ["--literal-pathspecs", *args]
        async with self._slots:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=_git_env(),
            )
            assert proc.stdout is not None
            out = bytearray()
            cut = False
            try:
                async with asyncio.timeout(GIT_TIMEOUT_S):
                    while chunk := await proc.stdout.read(65536):
                        out += chunk
                        if len(out) > limit:
                            cut = True
                            break
                    if cut:
                        with contextlib.suppress(ProcessLookupError):
                            proc.kill()
                    code = await proc.wait()
            except TimeoutError as exc:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()
                raise GitError(f"git {args[0]} timed out") from exc
        if code != 0 and not cut:
            raise GitError(f"git {args[0]} exited with {code}")
        return bytes(out[:limit]), cut

    async def resolve(self, ref: str) -> str:
        """The commit a `gen-N`, `exp-N` or full sha names; 400 if malformed, 404 if absent."""
        match = _REF.fullmatch(ref)
        if match is None:
            raise BadRequest(f"bad ref {ref!r}: expected gen-N, exp-N or a 40-hex sha")
        spec = f"refs/darwin/{ref}" if match.group(1) else ref
        try:
            out, _ = await self._git("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}")
        except GitError as exc:
            raise NotFound(f"unknown ref {ref!r}") from exc
        return out.decode().strip()

    async def _entries(self, commit: str, *paths: str) -> list[tuple[str, str, str, int, str]]:
        """ls-tree as (mode, type, object, size, path); a cut listing drops its last entry."""
        args = ["ls-tree", "-l", "-z", "--full-tree"]
        args += ["-r", commit] if not paths else [commit, "--", *paths]
        out, cut = await self._git(*args)
        records = out.split(b"\0")
        records = records[:-1]  # the last one is empty, or partial when cut
        entries = []
        for record in records:
            meta, _, raw_path = record.partition(b"\t")
            mode, kind, obj, size = meta.decode().split(maxsplit=3)
            path = raw_path.decode("utf-8", errors="replace")
            entries.append((mode, kind, obj, int(size) if size.isdigit() else 0, path))
        return entries

    async def tree(self, commit: str) -> list[dict[str, Any]]:
        entries = await self._entries(commit)
        files = [
            {"path": path, "size": size}
            for _, kind, _, size, path in entries
            if kind == "blob" and not hidden(path)
        ]
        return sorted(files, key=lambda f: f["path"])

    async def file(self, commit: str, path: str) -> dict[str, Any]:
        check_path(path)
        found = [e for e in await self._entries(commit, path) if e[4] == path]
        if not found or found[0][1] != "blob" or hidden(path):
            raise NotFound(f"no file {path!r} at {commit}")
        _, _, obj, size, _ = found[0]
        data, _ = await self._git("cat-file", "blob", obj, limit=MAX_TEXT_BYTES)
        truncated = size > len(data)
        text = _text(data, complete=not truncated)
        return {
            "path": path,
            "size": size,
            "binary": text is None,
            "truncated": truncated and text is not None,
            "content": text,
        }

    async def diff(self, base: str, head: str) -> list[dict[str, Any]]:
        key = (base, head)
        if key in self._diffs:
            self._diffs.move_to_end(key)
            return self._diffs[key]
        files = await self._diff(base, head)
        self._diffs[key] = files
        if len(self._diffs) > self._cache_size:
            self._diffs.popitem(last=False)
        return files

    async def _diff(self, base: str, head: str) -> list[dict[str, Any]]:
        common = ["-M", "--no-color", "--no-ext-diff", "--no-textconv"]
        names, _ = await self._git("diff", "-z", "--name-status", *common, base, head)
        stats, _ = await self._git("diff", "-z", "--numstat", *common, base, head)
        counts = _numstat(stats)
        changes = []
        fields = names.decode("utf-8", errors="replace").split("\0")
        i = 0
        while i + 1 < len(fields):
            letter = fields[i][:1]
            paths = fields[i + 1 : i + 3] if letter in {"R", "C"} else fields[i + 1 : i + 2]
            i += 1 + len(paths)
            if any(hidden(p) for p in paths):
                continue
            added, deleted, binary = counts.get(paths[-1], (0, 0, False))
            status = _STATUS.get(letter, "modified")
            changes.append((paths, status, added, deleted, binary))

        async def patch(index: int, paths: list[str], binary: bool) -> str:
            if binary:
                return ""
            if index >= MAX_PATCHED_FILES:
                return TRUNCATED
            out, cut = await self._git("diff", *common, base, head, "--", *paths,
                                       limit=MAX_PATCH_BYTES)  # fmt: skip
            text = out.decode("utf-8", errors="replace")
            return text[: text.rfind("\n") + 1] + TRUNCATED if cut else text

        patches = await asyncio.gather(
            *(patch(n, paths, binary) for n, (paths, _, _, _, binary) in enumerate(changes))
        )
        return [
            {
                "path": paths[-1],
                "status": status,
                "additions": added,
                "deletions": deleted,
                "patch": text,
            }
            for (paths, status, added, deleted, _), text in zip(changes, patches, strict=True)
        ]


def _numstat(out: bytes) -> dict[str, tuple[int, int, bool]]:
    """`diff --numstat -z`, by final path: (additions, deletions, binary)."""
    counts: dict[str, tuple[int, int, bool]] = {}
    fields = out.decode("utf-8", errors="replace").split("\0")
    i = 0
    while i < len(fields) and fields[i]:
        added, deleted, path = fields[i].split("\t", 2)
        if path:
            i += 1
        else:  # a rename: the old and the new path follow
            path = fields[i + 2]
            i += 3
        binary = added == "-"
        counts[path] = (0 if binary else int(added), 0 if binary else int(deleted), binary)
    return counts


def _text(data: bytes, *, complete: bool) -> str | None:
    """The text of a blob, or None when it looks binary (NUL early on, or not UTF-8)."""
    if b"\0" in data[:BINARY_SNIFF_BYTES]:
        return None
    try:
        # A cut blob may end inside a character: the incremental decoder holds those bytes.
        return codecs.getincrementaldecoder("utf-8")().decode(data, final=complete)
    except UnicodeDecodeError:
        return None
