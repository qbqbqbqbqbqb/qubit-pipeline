import random
import asyncio
import time

from scripts.core.base_module import BaseModule
from scripts.utils.log_utils import get_logger

class MonologueModule(BaseModule):
    def __init__(self, signals, queue_manager, response_generator, memory_manager=None,
                 max_monologues_between_chats=1, starters=None):
        super().__init__("MonologueModule", logger=get_logger("MonologueModule"))
        self.signals = signals
        self.queue_manager = queue_manager
        self.response_generator = response_generator
        self.max_monologues_between_chats = max_monologues_between_chats
        self.monologue_running = True
        self.starters = starters or [
            "Tell me something interesting.",
            "What's on your mind?",
            "Let's talk about something fun.",
        ]

    async def _should_pause(self):
        if not self.signals.monologue_enabled or not self.monologue_running:
            self.logger.debug("[MonologueModule] Paused due to signals or flags")
            return True
        return False

    async def _wait_for_chat_queue_processed(self):
        self.logger.debug("[MonologueModule] Max monologues reached with chat queue not empty, waiting...")
        while self.queue_manager.chat_queue.qsize() > 0 and not self.signals.terminate:
            await asyncio.sleep(1)
        self.queue_manager.consecutive_monologues = 0
        self.logger.debug("[MonologueModule] Chat queue processed, resuming monologue")

    async def _generate_monologue_response(self):
        starter = random.choice(self.starters)
        try:
            response = await self.response_generator.generate_response_safely(starter)
            return response
        except Exception as e:
            self.logger.error(f"[MonologueModule] Error generating response: {e}")
            return None

    async def _process_monologue_response(self, response, chat_queue_size):
        if not response or not response.strip():
            await asyncio.sleep(5)
            return False

        await self.queue_manager.monologue_queue.put({"type": "monologue", "text": response})
        self.logger.info(f"[MonologueModule] Queued monologue: {response}")

        if chat_queue_size > 0:
            self.queue_manager.consecutive_monologues += 1

        return True

    async def run(self):
        self.logger.info("[MonologueModule] Started")
        try:
            while not self.signals.terminate:
                self.logger.debug(
                    f"[MonologueModule] Loop: monologue_enabled={self.signals.monologue_enabled}, "
                    f"monologue_running={self.monologue_running}, "
                    f"consecutive_monologues={self.queue_manager.consecutive_monologues}, "
                    f"chat_queue_size={self.queue_manager.chat_queue.qsize()}"
                )

                if await self._should_pause():
                    await asyncio.sleep(1)
                    continue

                chat_queue_size = self.queue_manager.chat_queue.qsize()

                if chat_queue_size > 0 and self.queue_manager.consecutive_monologues >= self.max_monologues_between_chats:
                    await self._wait_for_chat_queue_processed()
                    continue

                response = await self._generate_monologue_response()
                processed = await self._process_monologue_response(response, chat_queue_size)
                if not processed:
                    continue

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            self.logger.info("[MonologueModule] Cancelled")
            raise

    def pause(self):
        self.logger.info("[MonologueModule] Paused")
        self.monologue_running = False
        self.signals.monologue_enabled = False

    def resume(self):
        self.logger.info("[MonologueModule] Resumed")
        self.monologue_running = True
        self.signals.monologue_enabled = True

    async def stop(self):
        self.logger.info("[MonologueModule] Stopping...")
        self.monologue_running = False
        self.signals.monologue_enabled = False
        await super().stop()
        self.logger.info("[MonologueModule] Stopped")
