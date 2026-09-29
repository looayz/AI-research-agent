"""In-process wake-up signal for the SSE endpoint.

Events are persisted in the database (the source of truth, which also works
across several workers). This bus only lets an SSE stream running in the same
process react immediately instead of waiting for its next polling tick.
"""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class EventBus:
    def __init__(self) -> None:
        self._waiters: dict[str, set[asyncio.Event]] = defaultdict(set)

    def publish(self, research_id: str) -> None:
        for waiter in self._waiters.get(research_id, ()):
            waiter.set()

    @asynccontextmanager
    async def subscribe(self, research_id: str) -> AsyncIterator[asyncio.Event]:
        waiter = asyncio.Event()
        self._waiters[research_id].add(waiter)
        try:
            yield waiter
        finally:
            waiters = self._waiters.get(research_id)
            if waiters is not None:
                waiters.discard(waiter)
                if not waiters:
                    self._waiters.pop(research_id, None)


event_bus = EventBus()
