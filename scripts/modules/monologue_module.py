import random
import asyncio
from scripts.core.base_module import BaseModule
from scripts.utils.log_utils import get_logger

class MonologueModule(BaseModule):
    def __init__(self, signals, queue_manager, response_generator, 
                 starters=None):
        super().__init__("MonologueModule", logger=get_logger("MonologueModule"))
        self.signals = signals
        self.queue_manager = queue_manager
        self.response_generator = response_generator
        self.monologue_running = True
        self.starters = starters or [
            "Tell me something interesting.",
            "What's on your mind?",
            "Let's talk about something fun.",
        ]

    async def _should_pause(self):
        if not self.signals.monologue_enabled or not self.monologue_running:
            #self.logger.debug("[MonologueModule] Paused due to signals or flags")
            return True
        return False

    async def _generate_monologue_response(self):
        starter = random.choice(self.starters)
        try:
            response = await self.response_generator.generate_response_safely(starter)
            return response
        except Exception as e:
            self.logger.error(f"[MonologueModule] Error generating response: {e}")
            return None

    async def _process_monologue_response(self, response):
        if not response or not response.strip():
            await asyncio.sleep(5)
            return False

        await self.queue_manager.process_new_monologue(response)
        self.logger.info(f"[MonologueModule] Queued monologue: {response}")
        return True

    async def run(self):
        self.logger.info("[MonologueModule] Started")
        try:
            while not self.signals.terminate:
                if await self._should_pause():
                    await asyncio.sleep(1)
                    continue

                response = await self._generate_monologue_response()
                await self._process_monologue_response(response)
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
