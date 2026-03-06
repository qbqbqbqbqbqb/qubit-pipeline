import asyncio

class RuntimeState:

    def __init__(self):
        self.shutdown = asyncio.Event()

        self.features = {
            "twitch": True,
            "kick": True,
            "youtube": True,
            "stt": True,
            "chat": True,
            "raid": True,
            "follow": True,
            "subs": True,
            "monologue": True
        }

        self.ai_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()