import asyncio
from typing import Any, Optional

from scripts.io.log_utils import get_logger
logger = get_logger("QueueManager")
from queue import Queue

MAX_CONSECUTIVE_MONOLOGUES = 3 

class QueueManager():
    def __init__(self):
        self.message_queue = Queue()
        self.monologue_queue = Queue()
        self.speech_queue = Queue()
        self.unprocessed_message_queue = Queue()

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
        logger.info(f"[Stop] Cleared {cleared_unprocessed_messages} items from message queue.")
        cleared_messages = self.clear_queues(self.message_queue)
        logger.info(f"[Stop] Cleared {cleared_messages} items from message queue.")
        cleared_speech = self.clear_queues(self.speech_queue)
        logger.info(f"[Stop] Cleared {cleared_speech} items from message queue.")