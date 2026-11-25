"""One poller for every live viewer.

The dashboard is public: each open page holding its own loop over the ledger and the
match files would make the server's load grow with the audience. A single task reads once a
second and fans the changes out to every subscriber; a page that falls behind is dropped
(the browser reconnects and gets a fresh start).
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from typing import Any

from darwin.ledger import queries
from darwin.ledger.store import Ledger

log = logging.getLogger(__name__)

TICK_S = 1.0
MAX_SUBSCRIBERS = 300
QUEUE_SIZE = 100


class Full(Exception):
    pass


class Hub:
    def __init__(self, ledger: Ledger, readers: dict[str, Callable[[], Any]]) -> None:
        self.ledger = ledger
        self.readers = readers
        self.subscribers: set[asyncio.Queue[str]] = set()
        self.snapshot: dict[str, str] = {}  # last value of each reader, for new subscribers
        self.last_event_id = 0
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.last_event_id = await queries.last_event_id(self.ledger)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def subscribe(self) -> asyncio.Queue[str]:
        if len(self.subscribers) >= MAX_SUBSCRIBERS:
            raise Full
        queue: asyncio.Queue[str] = asyncio.Queue(QUEUE_SIZE)
        for name, encoded in self.snapshot.items():
            queue.put_nowait(f"event: {name}\ndata: {encoded}\n\n")
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self.subscribers.discard(queue)

    def _publish(self, message: str) -> None:
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                self.subscribers.discard(queue)  # too slow: it will reconnect

    async def _run(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception:
                log.exception("live hub tick failed")
            await asyncio.sleep(TICK_S)

    async def _tick(self) -> None:
        for event in await queries.events_after(self.ledger, self.last_event_id):
            self.last_event_id = event["id"]
            self._publish(f"event: agent\ndata: {json.dumps(event)}\n\n")
        for name, read in self.readers.items():
            encoded = json.dumps(await asyncio.to_thread(read))
            if encoded != self.snapshot.get(name):
                self.snapshot[name] = encoded
                self._publish(f"event: {name}\ndata: {encoded}\n\n")
