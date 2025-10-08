import asyncio

class Signals:
    def __init__(self):
        self.terminate = False
        self.enable_input = True
        self.enable_queue_processing = True
        self.enable_response_generation = True
        self.enable_tts = True
        self.enable_twitch = True
        self.enable_monologue = False
        self.command_queue = asyncio.Queue()
        self.is_human_speaking = False
        self.ai_thinking = False
        self.chat_arrived = asyncio.Event()
        self.ai_speaking = asyncio.Event()