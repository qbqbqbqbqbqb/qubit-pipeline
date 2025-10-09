import asyncio
from scripts.core.base_module import BaseModule
from scripts.utils.log_utils import get_logger
import datetime as dt

class QueueProcessor(BaseModule):
    def __init__(self, queue_manager, prune_after_seconds=300):
        super().__init__("QueueProcessor", logger=get_logger("QueueProcessor"))
        self.queue_manager = queue_manager
        self.prune_after_seconds = prune_after_seconds
        self.running = False

    async def _prune_old_items(self):
        now = dt.datetime.now()

        def too_old(item):
            ts = item.get("timestamp")
            if not isinstance(ts, dt.datetime):
                return False
            return (now - ts).total_seconds() > self.prune_after_seconds

        new_processing_queue = asyncio.Queue()
        while not self.queue_manager.processing_queue.empty():
            item = await self.queue_manager.processing_queue.get()
            if too_old(item):
                self.logger.info(f"[QueueProcessor] Dropping old processing item: {item}")
            else:
                await new_processing_queue.put(item)
            self.queue_manager.processing_queue.task_done()
        self.queue_manager.processing_queue = new_processing_queue

    async def _prune_speech_queue(self, max_age_seconds=300):
        now = dt.datetime.now()

        def too_old(item):
            ts = item.get("timestamp")
            if not ts:
                return False

            if isinstance(ts, int):
                try:
                    ts = dt.datetime.fromtimestamp(ts / 1000)
                except Exception as e:
                    self.logger.warning(f"[QueueProcessor] Invalid int timestamp in speech_queue: {ts} ({e})")
                    return False

            if not isinstance(ts, dt.datetime):
                self.logger.warning(f"[QueueProcessor] Invalid timestamp type in speech_queue: {type(ts)} — skipping")
                return False

            return (now - ts).total_seconds() > max_age_seconds

        new_speech_queue = asyncio.Queue()
        while not self.queue_manager.speech_queue.empty():
            item = await self.queue_manager.speech_queue.get()
            if isinstance(item, dict) and too_old(item):
                self.logger.info(f"[QueueProcessor] Dropping old speech queue item: {item}")
                self.queue_manager.speech_queue.task_done()
            else:
                await new_speech_queue.put(item)
                self.queue_manager.speech_queue.task_done()

        self.queue_manager.speech_queue = new_speech_queue

    async def run(self):
        self.logger.info("[QueueProcessor] Started")
        self.running = True

        try:
            while self.running and not self.queue_manager.signals.terminate:
                self.logger.debug("[QueueProcessor] Starting processing cycle")
                await self._prune_old_items()
                await self._prune_speech_queue()

                await self.transfer_chats_to_processing()
                await self.transfer_monologues_to_processing()

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("[QueueProcessor] Cancelled")
            raise


    async def stop(self):
        self.logger.info("[QueueProcessor] Stopping...")
        self.running = False
        await super().stop()
        self.logger.info("[QueueProcessor] Stopped")

    async def transfer_chats_to_processing(self):
        while not self.queue_manager.chat_queue.empty():
            chat_msg = await self.queue_manager.chat_queue.get()
            await self.queue_manager.processing_queue.put(chat_msg)
            self.queue_manager.consecutive_monologues = 0
            self.queue_manager.chat_queue.task_done()
            self.logger.info(f"[QueueProcessor] Chat moved to processing: {chat_msg.get('user')} - {chat_msg.get('prompt')[:50]}...")

    async def transfer_monologues_to_processing(self):
        while not self.queue_manager.monologue_queue.empty():
            if (not self.queue_manager.chat_queue.empty() and
                self.queue_manager.consecutive_monologues >= self.queue_manager.max_monologues_between_chats):
                self.logger.debug("[QueueProcessor] Monologue limit reached with pending chat — pausing monologues")
                break

            monologue_msg = await self.queue_manager.monologue_queue.get()
            await self.queue_manager.processing_queue.put(monologue_msg)
            self.queue_manager.consecutive_monologues += 1
            self.queue_manager.monologue_queue.task_done()
            self.logger.debug("[QueueProcessor] Monologue moved to processing")
