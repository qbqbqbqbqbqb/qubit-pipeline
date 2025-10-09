import asyncio
import random
from scripts2.modules.base_module import BaseModule

class MonologueModule(BaseModule):
    def __init__(self, signals, event_broker, monologue_enabled=True):
        super().__init__(name="MonologueModule")
        self.signals = signals
        self.monologue_enabled = monologue_enabled
        self.event_broker = event_broker
        self.monologue_texts = [
            "Hmm, let me think about this...",
            "You know, I've been pondering the mysteries of the universe lately.",
            "Sometimes I wonder what it would be like to have a conversation with myself.",
            "Did you ever notice how time flies when you're not paying attention?",
            "I should probably clean up my digital thoughts one day.",
            "Autonomous musings are quite the experience."
        ]

    async def start(self):
        if not self.monologue_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        await super().start()

    async def run(self):
        await super().run()

        while self._running:
            self.logger.debug(f"{self.name} loop running, _running={self._running}")
            try:
                monologue_text = random.choice(self.monologue_texts) 
                self.event_broker.publish_event({
                    "type": "monologue",
                    "text": monologue_text
                })
                self.logger.debug(f"Published monologue prompt: {monologue_text}")
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Exception in MonologueModule run loop: {e}")
                
    async def stop(self):
        await super().stop()
