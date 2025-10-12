import asyncio
from datetime import datetime
import uuid
from typing import Dict

from scripts2.modules.base_module import BaseModule
from scripts2.rag.chat_history_manager import ChatHistoryManager
from scripts2.rag.memory_lifecycle_manager import MemoryLifecycleManager
from scripts2.rag.reflection_generator import ReflectionGenerator

"""

This module handles asynchronous event processing for memory management and reflection generation.

It provides the AsyncEventHandler class which processes memory events asynchronously,

manages chat history, and triggers reflections when thresholds are met.

"""

class AsyncEventHandler(BaseModule):
    """

    Asynchronous event handler for processing memory-related events.

    This class extends BaseModule and manages a queue of memory events, performing

    background processing such as memory decay, reflection generation, and event publishing.

    Attributes:

        event_broker: The central event broker for publishing events.

        chat_history_manager (ChatHistoryManager): Manager for chat history operations.

        memory_lifecycle_manager (MemoryLifecycleManager): Manager for memory lifecycle operations.

        reflection_generator (ReflectionGenerator): Generator for reflection QA pairs.

        reflection_threshold (int): Number of messages before triggering reflection.

        queue (asyncio.Queue): Queue for holding memory events.

        loop: The event loop.

        message_counter (int): Counter for processed messages.

        _last_memory_snapshot: Snapshot of last memory state.

    """

    def __init__(self, event_broker, chat_history_manager: ChatHistoryManager, memory_lifecycle_manager: MemoryLifecycleManager, reflection_generator: ReflectionGenerator, reflection_threshold: int = 20):
        super().__init__("AsyncEventHandler")
        self.event_broker = event_broker
        self.chat_history_manager = chat_history_manager
        self.memory_lifecycle_manager = memory_lifecycle_manager
        self.reflection_generator = reflection_generator
        self.reflection_threshold = reflection_threshold

        self.queue = asyncio.Queue()
        self.loop = None
        self.message_counter = 0
        self._last_memory_snapshot = None

    async def start(self):
        """

        Start the event handler by setting the event loop.

        """
        self.loop = asyncio.get_running_loop()
        await super().start()

    async def run(self):
        """

        Run the main event loop for processing memory events and cleanup.

        Manages the queue of events and schedules periodic memory cleanup.

        """
        self.logger.info("[run] AsyncEventHandler loop started.")

        cleanup_interval = 60
        next_cleanup = asyncio.create_task(self._schedule_cleanup(cleanup_interval))

        while self._running:
            try:
                queue_get_task = asyncio.create_task(self.queue.get())

                done, pending = await asyncio.wait(
                    [queue_get_task, next_cleanup],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    if task is next_cleanup:
                        self.memory_lifecycle_manager.decay_old_memories()
                        self.memory_lifecycle_manager.decay_chat_memories()
                        self.logger.info("Memory cleanup completed")
                        next_cleanup = asyncio.create_task(self._schedule_cleanup(cleanup_interval))
                    elif task is queue_get_task:
                        message = task.result()
                        await self._handle_memory_event(message)
                        self.queue.task_done()

            except Exception as e:
                self.logger.error(f"[run] Error in loop: {e}")

    async def _schedule_cleanup(self, delay: int):
        """

        Schedule a cleanup operation after a delay.

        Args:

            delay (int): Delay in seconds.

        """
        await asyncio.sleep(delay)

    async def _handle_memory_event(self, data: Dict):
        """

        Handle a memory event by adding it to chat history and checking for reflection.

        Args:

            data (Dict): Event data containing role, content, etc.

        """
        self.chat_history_manager.add_conversation_item_sync(**data)
        self.message_counter += 1
        self.update_memories_if_changed()

        if self.message_counter >= self.reflection_threshold:
            self.logger.info(f"[Reflection] Triggering after {self.message_counter} messages")
            asyncio.create_task(self._perform_and_store_reflection())

    async def _perform_and_store_reflection(self):
        """

        Perform reflection generation and store the resulting QA pairs in chat history.

        Generates QA pairs, stores them as memories, and resets the message counter.

        """
        qa_pairs = await self.reflection_generator._perform_reflection()

        for i, (question, answer) in enumerate(qa_pairs, 1):
            qa_memory = f"Q: {question}\nA: {answer}"
            reflection_id = str(uuid.uuid4())

            self.chat_history_manager.collection.upsert(
                ids=[reflection_id],
                documents=[qa_memory],
                metadatas=[{
                    "type": "short-term",
                    "reflection_batch": self.message_counter,
                    "question": question,
                    "answer": answer,
                    "created_at": datetime.now().isoformat()
                }]
            )
            self.logger.info(f"Stored reflection memory Q{i}: {question[:50]}...")

        self.message_counter = 0
        self.logger.info(f"[Reflection] Reflection process completed successfully - stored {len(qa_pairs)} new memories")

    def update_memories_if_changed(self):
        """

        Check if memories have changed and publish an update event if so.

        Compares current memory snapshot with last snapshot and publishes event on change.

        """
        current_snapshot = self.chat_history_manager.get_recent_memories()

        snapshot_id = str(current_snapshot)

        if snapshot_id != self._last_memory_snapshot:
            self._last_memory_snapshot = snapshot_id
            self.event_broker.publish_event({
                "type": "memories_updated",
                "data": current_snapshot
            })

    def submit_spoken_memory(self, role: str, content: str, user_id: str = None, metadata: Dict = None):
        """

        Submit a spoken memory event to the queue.

        Args:

            role (str): The role of the message (e.g., 'user', 'qubit').

            content (str): The content of the message.

            user_id (str, optional): The user ID. Defaults to None.

            metadata (Dict, optional): Additional metadata. Defaults to None.

        """
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.queue.put({
                    "role": role,
                    "content": content,
                    "user_id": user_id,
                    "metadata": metadata
                }),
                self.loop
            )
        else:
            self.logger.warning("submit_spoken_memory called before loop is set.")