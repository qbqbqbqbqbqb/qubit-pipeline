import asyncio

class Signals:
    def __init__(self):
        self.terminate = asyncio.Event()
        self.is_human_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
        self.ai_speaking = asyncio.Event()

        self.response_generator_ready = asyncio.Event()
        self.tts_module_ready = asyncio.Event()


