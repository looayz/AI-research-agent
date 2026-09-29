"""Registry of the research pipelines running in this process.

Keeping a handle on each asyncio task lets a cancel request stop a pipeline
immediately (even in the middle of an LLM call) and lets the app cancel
everything cleanly on shutdown.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class ResearchTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def start(self, research_id: str, factory: Callable[[], Awaitable[None]]) -> None:
        if self.is_running(research_id):
            raise RuntimeError(f"Research {research_id} is already running")
        task = asyncio.create_task(factory(), name=f"research:{research_id}")
        self._tasks[research_id] = task
        task.add_done_callback(lambda t: self._on_done(research_id, t))

    def _on_done(self, research_id: str, task: asyncio.Task) -> None:
        if self._tasks.get(research_id) is task:
            self._tasks.pop(research_id, None)
        if not task.cancelled() and task.exception() is not None:
            logger.error("Research %s crashed", research_id, exc_info=task.exception())

    def is_running(self, research_id: str) -> bool:
        task = self._tasks.get(research_id)
        return task is not None and not task.done()

    def cancel(self, research_id: str) -> bool:
        task = self._tasks.get(research_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    async def wait(self, research_id: str) -> None:
        task = self._tasks.get(research_id)
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)

    async def shutdown(self, timeout: float = 5.0) -> None:
        tasks = [t for t in self._tasks.values() if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)


task_manager = ResearchTaskManager()
