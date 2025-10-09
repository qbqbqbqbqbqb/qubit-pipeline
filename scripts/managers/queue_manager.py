import asyncio
import datetime
from scripts.utils.log_utils import get_logger

class QueueManager:
    def __init__(self, signals):
        self.logger = get_logger("QueueManager")
        self.chat_queue = asyncio.Queue()
        self.monologue_queue = asyncio.Queue()
        self.processing_queue = asyncio.Queue()
        self.speech_queue = asyncio.Queue()
        self.max_monologues_between_chats = 3 
        self.signals = signals

    async def process_new_chat_message(self, msg):
        if "timestamp" not in msg or not isinstance(msg["timestamp"], datetime.datetime):
            msg["timestamp"] = datetime.datetime.now(datetime.timezone.utc)

        msg["type"] = "chat_message"
        await self.chat_queue.put(msg)

    async def process_new_monologue(self, monologue_text):
        msg = {
            "text": monologue_text,
            "type": "monologue",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }
        await self.monologue_queue.put(msg)

    async def enqueue_speech(self, text: str, item_type: str = "ai_response", timestamp=None):
        msg = {
            "text": text,
            "type": item_type,
            "timestamp": timestamp or datetime.datetime.now(datetime.timezone.utc)
        }
        await self.speech_queue.put(msg)
