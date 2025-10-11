"""
Signals module for asynchronous event coordination.

This module defines the Signals class, which provides asyncio Event objects
for coordinating various states and readiness signals across the application.
"""

import asyncio

class Signals:
    """
    Collection of asyncio Event objects for coordinating application states.

    Provides events for termination, speaking states, and module readiness.
    """
    def __init__(self):
        """
        Initializes the Signals instance with asyncio Event objects.
        """
        self.terminate = asyncio.Event()
        self.is_human_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
        self.ai_speaking = asyncio.Event()

        self.response_generator_ready = asyncio.Event()
        self.tts_module_ready = asyncio.Event()


