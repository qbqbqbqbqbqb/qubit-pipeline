"""Runtime state flags and async events for the application lifecycle."""

import asyncio


class RuntimeState:
    """Shared mutable state for the running application."""

    def __init__(self):
        self.shutdown = asyncio.Event()
        self.start = asyncio.Event()

        self.features = {
            "twitch": True,
            "kick": True,
            "youtube": True,
            "stt": True,
            "chat": True,
            "raid": True,
            "follow": True,
            "subs": True,
            "monologue": True,
            "vtube_studio": True
        }

        self.ai_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
