# for adding signals to link to frontend
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

        self.twitch_enabled = asyncio.Event()
        self.youtube_enabled = asyncio.Event()
        self.kick_enabled = asyncio.Event()
        self.monologue_enabled = asyncio.Event()
        self.speech_to_text_enabled = asyncio.Event()

        self.core_ready_event = asyncio.Event()
        self.frontend_ready_event = asyncio.Event()

        self.chat_enabled = asyncio.Event()
        self.raid_enabled = asyncio.Event()
        self.follow_enabled = asyncio.Event()
        self.subs_enabled = asyncio.Event()



