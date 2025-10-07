import asyncio

class Signals:
    def __init__(self):
        self.terminate = False
        self.monologue_enabled = False
        self.command_queue = asyncio.Queue()
        self.is_human_speaking = False
        self.ai_thinking = False
        self.chat_arrived = asyncio.Event()
        self.tts_finished = asyncio.Event()

