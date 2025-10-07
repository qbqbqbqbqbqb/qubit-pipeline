import asyncio
from scripts.utils.log_utils import get_logger

class QueueManager:
    def __init__(self):
        self.logger = get_logger("QueueManager")
        self.monologue_queue = asyncio.Queue()
        self.chat_queue = asyncio.Queue()
        self.consecutive_monologues = 0
        self.chat_arrived = asyncio.Event()

    async def process_new_chat_message(self, msg):
        self.logger.debug("[QueueManager] New chat message received, resetting consecutive_monologues.")
        self.consecutive_monologues = 0
        self.chat_arrived.set()
        await self.chat_queue.put(msg)