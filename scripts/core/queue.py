import asyncio
from typing import Any, Optional

from log_utils import get_logger
logger = get_logger("QueueManager")

class Queue:
    def __init__(self,
                 maxsize: int = 0,
                 cap: Optional[int] = None,
                 ):
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._paused = asyncio.Event()
        self._paused.set()

        self._cap: Optional[int] = cap

    async def _wait_if_paused(self) -> None:
        if not self._paused.is_set():
            logger.debug("q paused")
        await self._paused.wait()

    async def put(self, item: Any) -> None:

        await self._wait_if_paused()

        if self._cap is not None:
            await self._reduce(item)

        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning(f"q full - dropping {item}")

    async def get(self) -> Any:
        return await self._queue.get()
    
    def task_done(self) -> None:
        self._queue.task_done()

    def empty(self) -> bool:
        return self._queue.empty()

    async def pause(self) -> None:
        if self._paused.is_set():
            self._paused.clear()
            logger.info("paused")

    async def resume(self) -> None:
        if not self._paused.is_set():
            self._paused.set()
            logger.info("resumed")

    def qsize(self) -> int:
        return self._queue.qsize()
    
    async def _reduce(self):
        while self.qsize() > self._cap:
            try:
                dropped = self._queue.get_nowait()
                self._queue.task_done()
                logger.debug(f"over cap. dropped oldest in queue")
            except asyncio.QueueEmpty:
                logger.warning("queue empty")