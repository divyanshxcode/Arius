"""In-process fan-out for SSE.

One publisher (the pump / API handlers), N subscribers (browser tabs).
Slow subscribers are dropped rather than blocking the tick.
"""

from __future__ import annotations

import asyncio
from collections import deque


class EventBus:
    def __init__(self, backlog: int = 300) -> None:
        self._subs: set[asyncio.Queue] = set()
        self._backlog: deque[dict] = deque(maxlen=backlog)

    def publish(self, event: dict) -> None:
        self._backlog.append(event)
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # a stuck tab must never stall the simulation
                self._subs.discard(q)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    @property
    def backlog(self) -> list[dict]:
        return list(self._backlog)

    @property
    def subscribers(self) -> int:
        return len(self._subs)


bus = EventBus()
