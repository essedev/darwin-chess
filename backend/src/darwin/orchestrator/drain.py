"""Draining before a restart: `make deploy` asks core to stop taking new work, waits until
what is running has ended, then restarts it.

The request is a file, `data/control/drain`, written by the host (the data directory is
mounted at the same path). Core answers with `data/control/drained` once no agent session
and no Lichess game is running; from then on it only waits to be stopped. A trial in progress
is not waited for: the referee judges it again from the start after the restart, which
costs CPU time and nothing else.
"""

from pathlib import Path

from darwin.config import Settings

CHECK_EVERY_S = 2.0


class Drain:
    def __init__(self, settings: Settings) -> None:
        self.dir = settings.data_dir / "control"

    @property
    def request(self) -> Path:
        return self.dir / "drain"

    @property
    def done(self) -> Path:
        return self.dir / "drained"

    def requested(self) -> bool:
        return self.request.exists()

    def mark_done(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.done.touch()

    def reset(self) -> None:
        """At startup: a request left by the previous process is not for this one."""
        self.request.unlink(missing_ok=True)
        self.done.unlink(missing_ok=True)
