import asyncio
from scripts.utils.log_utils import get_logger

class QueueManager:
    def __init__(self):
        self.twitch_chat_prompt_queue = asyncio.Queue()
        self.twitch_event_prompt_queue = asyncio.Queue() # implement later do not forget
        self.monologue_prompt_queue = asyncio.Queue()
        self.response_processing_queue = asyncio.PriorityQueue()
        self.logger = get_logger("QueueManager")

        self._merge_task = None

    async def process_new_prompt_from_twitch_chat(self, author, message):
        unprocessed_item = {
            "user": author,
            "message": message,
            "type": "chat_message"
        }
        await self.twitch_chat_prompt_queue.put(unprocessed_item)

    async def process_new_prompt_from_monologue_generation(self, monologue_text):
        unprocessed_item = {
            "text": monologue_text,
            "type": "monologue",
        }
        await self.monologue_prompt_queue.put(unprocessed_item)

    async def start_merging_queues(self):
        if self._merge_task is None:
            self._merge_task = asyncio.create_task(self._merge_queues())

    async def _merge_queues(self):
        await asyncio.gather(
            self._forward_queue(self.twitch_chat_prompt_queue),
            self._forward_queue(self.monologue_prompt_queue)
        )

    async def _forward_queue(self, source_queue: asyncio.Queue):
        while True:
            item = await source_queue.get()
            self.logger.debug(f"[QueueManager] Forwarding item to response_processing_queue: {item}")

            priority = self._get_priority(item)
            await self.response_processing_queue.put((priority, item))

            source_queue.task_done()

    def _get_priority(self, item: dict) -> int:
        """
        Determine the priority for response processing.
        Lower number = higher priority.
        """
        item_type = item.get("type", "")
        text = item.get("text", "").lower()

        if item_type == "startup":
            return 1
        elif item_type == "chat_message":
            return 5
        elif item_type == "monologue":
            return 5
        else:
            return 10

    async def stop_merging_queues(self):
        if self._merge_task:
            self._merge_task.cancel()
            try:
                await self._merge_task
            except asyncio.CancelledError:
                pass
