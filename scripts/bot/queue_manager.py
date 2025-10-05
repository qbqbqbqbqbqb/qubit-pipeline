import asyncio
from typing import Any, Optional

from scripts.utils.log_utils import get_logger
logger = get_logger("QueueManager")

class Queue:
    """
    Enhanced asyncio.Queue with pause/resume functionality and capacity management.

    This queue supports:
    - Pausing/resuming operations to control flow
    - Capacity limits with automatic oldest-item removal
    - Async-safe operations for concurrent access
    """

    def __init__(self,
                 maxsize: int = 0,
                 cap: Optional[int] = None,
                 ):
        """
        Initialize the enhanced queue.

        Args:
            maxsize: Maximum queue size (0 = unlimited)
            cap: Capacity limit - when exceeded, oldest items are automatically removed
        """
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

MAX_CONSECUTIVE_MONOLOGUES = 3 

class QueueManager:
    """
    Manages multiple async queues for the VTuber bot's message processing pipeline.

    Coordinates three main queues:
    - message_queue: User chat messages waiting for AI processing
    - monologue_queue: AI-generated monologue text waiting for speech synthesis
    - speech_queue: Final speech items ready for TTS output

    Handles queue merging logic to prioritize user messages over monologues
    and prevent monologue spam during active conversations.
    """

    def __init__(self):
        self.message_queue = Queue()
        self.monologue_queue = Queue()
        self.speech_queue = Queue()

        self._consecutive_monologues = 0

        self._chat_arrived = asyncio.Event()
        self._chat_arrived.clear()
    
    async def enqueue_chat(self, item: dict) -> None:
        await self.message_queue.put(item)
        self._chat_arrived.set()
        logger.debug("chat queued")

    async def merge_queues(self) -> None:
            while True:
                if not self.message_queue.empty():
                    item = await self.message_queue.get()
                    self.message_queue.task_done()

                    self._consecutive_monologues = 0
                    self._chat_arrived.clear()
                    logger.debug("[merge_queues] Consumed chat – streak reset")

                    await self.speech_queue.put(item)
                    logger.debug(
                        f"[merge_queues] forwarded chat → speech "
                        f"([merge_queues] streak={self._consecutive_monologues})"
                    )
                    continue

                if not self.monologue_queue.empty():
                    if (
                        self._consecutive_monologues >= MAX_CONSECUTIVE_MONOLOGUES
                        and not self.message_queue.empty()
                    ):
                        logger.info(
                            f"[merge_queues] Consecutive monologue limit reached "
                            f"([merge_queues] {self._consecutive_monologues}); waiting for chat"
                        )
                        await self._chat_arrived.wait()
                        continue

                    item = await self.monologue_queue.get()
                    self.monologue_queue.task_done()
                    self._consecutive_monologues += 1

                    await self.speech_queue.put(item)
                    logger.debug(
                        f"[merge_queues] forwarded monologue to speech "
                        f"([merge_queues]streak={self._consecutive_monologues})"
                    )
                    continue

                await asyncio.sleep(0.1)

    async def reset_consecutive_counter(self) -> None:
        self._consecutive_monologues = 0
        self._chat_arrived.clear()
        logger.info("[merge_queues] Consecutive monologue counter reset")

    async def clear_queues(self, queue_placeholder: Any) -> int:
        cleared_items = 0
        while not queue_placeholder.empty():
            queue_placeholder.get()
            queue_placeholder.task_done()
            cleared_items += 1
        return cleared_items
    
    async def clear_all(self):
        cleared_unprocessed_messages = self.clear_queues(self.unprocessed_message_queue)
        logger.info(f"[Stop] Cleared {cleared_unprocessed_messages} items from unprocessed message queue.")
        cleared_messages = self.clear_queues(self.message_queue)
        logger.info(f"[Stop] Cleared {cleared_messages} items from message queue.")
        cleared_speech = self.clear_queues(self.speech_queue)
        logger.info(f"[Stop] Cleared {cleared_speech} items from speech queue.")