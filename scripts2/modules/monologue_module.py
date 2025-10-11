import asyncio
import datetime

import random
from scripts2.modules.base_module import BaseModule
from scripts2.config.config import MONOLOGUE_PROMPTS_FILE

"""

Monologue Module

This module provides the MonologueModule class, which is responsible for generating and publishing monologue prompts in the system. Monologues are periodic text outputs that can be used for conversational AI systems to maintain engagement or simulate thought processes.

"""

class MonologueModule(BaseModule):
    """

    MonologueModule class.

    This class inherits from BaseModule and handles the publication of monologue events at regular intervals. It randomly selects from a predefined list of monologue prompts and publishes them via the event broker.

    Attributes:
        signals: The signals object for communication.
        monologue_enabled (bool): Flag to enable or disable the module.
        event_broker: The central event broker for publishing events.
        monologue_texts: List of monologue prompt texts.

    """

    def __init__(self, signals, event_broker, monologue_enabled=True):
        """

        Initialize the MonologueModule.

        Args:
            signals: The signals object for inter-module communication.
            event_broker: The event broker for publishing and subscribing to events.
            monologue_enabled (bool): Whether to enable monologue generation. Defaults to True.

        """
        super().__init__(name="MonologueModule")
        self.signals = signals
        self.monologue_enabled = monologue_enabled
        self.event_broker = event_broker
        self.monologue_texts = MONOLOGUE_PROMPTS_FILE

    async def start(self):
        """

        Start the module.

        If monologue is enabled, calls the parent's start method. Otherwise, logs that it's disabled.

        """
        if not self.monologue_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        await super().start()

    async def run(self):
        """

        Main run loop for the module.

        Publishes a random monologue text as an event every 5 seconds while running.

        """
        await super().run()

        while self._running:
            self.logger.debug(f"{self.name} loop running, _running={self._running}")
            try:
                monologue_text = random.choice(self.monologue_texts) 
                self.event_broker.publish_event({
                    "type": "monologue",
                    "text": monologue_text,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                })
                self.logger.debug(f"Published monologue prompt: {monologue_text}")
                await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Exception in MonologueModule run loop: {e}")
                
    async def stop(self):
        """

        Stop the module.

        Calls the parent's stop method.

        """
        await super().stop()
