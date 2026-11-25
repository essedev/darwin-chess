"""A minimal UCI session with one engine container, used by the perft gate.

Games are played by fastchess, not here: this only needs the handshake, `position` and the
contract's `perft <depth>` command.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from darwin.config import Settings
from darwin.referee import docker
from darwin.referee.models import EngineSpec

STARTUP_TIMEOUT_S = 20.0


class EngineFault(Exception):
    """The engine broke the protocol: no answer in time, garbage, or it died."""


class UciSession:
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process

    def send(self, line: str) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(f"{line}\n".encode())

    async def read_line(self, timeout_s: float) -> str:
        assert self._process.stdout is not None
        try:
            raw = await asyncio.wait_for(self._process.stdout.readline(), timeout_s)
        except TimeoutError as exc:
            raise EngineFault(f"no answer within {timeout_s:g}s") from exc
        except ValueError as exc:  # a line longer than the stream limit
            raise EngineFault("output line too long") from exc
        if not raw:
            raise EngineFault("engine exited")
        return raw.decode(errors="replace").strip()

    async def read_until(self, prefix: str, timeout_s: float) -> list[str]:
        """Lines up to and including the first starting with `prefix`, within one deadline."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        lines: list[str] = []
        while True:
            line = await self.read_line(max(0.0, deadline - loop.time()))
            lines.append(line)
            if line.startswith(prefix):
                return lines

    async def handshake(self) -> None:
        self.send("uci")
        await self.read_until("uciok", STARTUP_TIMEOUT_S)
        self.send("isready")
        await self.read_until("readyok", STARTUP_TIMEOUT_S)


@contextlib.asynccontextmanager
async def session(settings: Settings, spec: EngineSpec) -> AsyncIterator[UciSession]:
    run_id = docker.new_run_id()
    process = await asyncio.create_subprocess_exec(
        *docker.engine_argv(settings, spec, run_id),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        uci = UciSession(process)
        await uci.handshake()
        yield uci
    finally:
        if process.returncode is None:
            with contextlib.suppress(ConnectionError):
                UciSession(process).send("quit")
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                process.kill()
                await process.wait()
        await docker.remove_run_containers(settings, run_id)
