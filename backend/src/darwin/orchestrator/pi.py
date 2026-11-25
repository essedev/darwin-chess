"""pi in RPC mode: a child process spoken to in JSONL on stdin and stdout.

pi runs in an empty working folder with every kind of automatic loading off (project
config, extensions, skills, prompt templates, context files, MCP), so nothing the agent
writes can ever be loaded by it: only our extension is.
"""

import asyncio
import contextlib
import json
import logging
import os
import uuid
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from darwin.config import Settings

log = logging.getLogger(__name__)

STREAM_LIMIT = 32 * 1024 * 1024  # one record can carry a whole file read by a tool
TOOLS = "read,write,edit,bash,perft_check,submit,experiments,run_job,lichess_losses"


class PiError(Exception):
    pass


def pi_argv(settings: Settings, system_prompt: Path) -> list[str]:
    agent = settings.agent_dir
    return [
        str(agent / "node_modules" / ".bin" / "pi"),
        "--mode", "rpc", "--no-session",
        "--no-approve", "--no-extensions", "-e", str(agent / "darwin-extension.ts"),
        "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-mcp", "--no-themes",
        "--tools", TOOLS,
        "--provider", settings.llm_provider, "--model", settings.llm_model,
        "--thinking", settings.llm_thinking,
        "--append-system-prompt", str(system_prompt),
    ]  # fmt: skip


class PiProcess:
    def __init__(self, settings: Settings, *, system_prompt: Path, workdir: Path,
                 extra_env: dict[str, str]) -> None:  # fmt: skip
        self._argv = pi_argv(settings, system_prompt)
        self._workdir = workdir
        home = settings.data_dir / "agent" / "pi-home"
        self._env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home),
            "PI_CODING_AGENT_DIR": str(home),
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "PI_CACHE_RETENTION": "long",
            **settings.llm_key_env(),
            **extra_env,
        }
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._stderr: deque[str] = deque(maxlen=50)
        self._tasks: list[asyncio.Task[None]] = []
        workdir.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        self._process = await asyncio.create_subprocess_exec(
            *self._argv, cwd=self._workdir, env=self._env, limit=STREAM_LIMIT,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )  # fmt: skip
        self._tasks = [asyncio.create_task(self._read_stdout()),
                       asyncio.create_task(self._read_stderr())]  # fmt: skip

    def stderr_tail(self) -> str:
        return "\n".join(self._stderr)

    async def _read_stdout(self) -> None:
        assert self._process and self._process.stdout
        while raw := await self._process.stdout.readline():  # splits on LF only
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("pi wrote a non-JSON line: %r", raw[:200])
                continue
            if record.get("type") == "response" and record.get("id") in self._pending:
                self._pending.pop(record["id"]).set_result(record)
            else:
                await self._events.put(record)
        for future in self._pending.values():
            future.set_exception(PiError(f"pi exited: {self.stderr_tail()[-500:]}"))
        self._pending.clear()
        await self._events.put(None)

    async def _read_stderr(self) -> None:
        assert self._process and self._process.stderr
        while raw := await self._process.stderr.readline():
            self._stderr.append(raw.decode(errors="replace").rstrip())

    async def command(self, command: dict[str, Any], timeout_s: float = 60) -> dict[str, Any]:
        assert self._process and self._process.stdin
        request_id = uuid.uuid4().hex
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        self._process.stdin.write(json.dumps({**command, "id": request_id}).encode() + b"\n")
        await self._process.stdin.drain()
        response = await asyncio.wait_for(future, timeout_s)
        if not response.get("success"):
            raise PiError(f"{command['type']} failed: {response.get('error')}")
        return response

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while (event := await self._events.get()) is not None:
            yield event

    async def prompt(self, message: str) -> None:
        await self.command({"type": "prompt", "message": message})

    async def abort(self) -> None:
        with contextlib.suppress(PiError, TimeoutError, ConnectionError):
            await self.command({"type": "abort"}, timeout_s=10)

    async def close(self, grace_s: float = 15) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin and not process.stdin.is_closing():
            process.stdin.close()  # orderly shutdown
        try:
            await asyncio.wait_for(process.wait(), grace_s)
        except TimeoutError:
            process.kill()
            await process.wait()
        for task in self._tasks:
            task.cancel()
