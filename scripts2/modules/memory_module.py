import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List
import uuid
import threading

import chromadb
from chromadb.config import Settings

from scripts2.modules.base_module import BaseModule
from scripts2.core.memory import Memory
from scripts2.config.config import MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION
from scripts2.modules.response_generator_module import ResponseGeneratorModule

from scripts2.rag.memory_storage import MemoryStorage
from scripts2.rag.user_profile_manager import UserProfileManager
from scripts2.rag.memory_lifecycle_manager import MemoryLifecycleManager
from scripts2.rag.reflection_generator import ReflectionGenerator
from scripts2.rag.chat_history_manager import ChatHistoryManager
from scripts2.rag.memory_context_provider import MemoryContextProvider
from scripts2.rag.statistics_reporter import StatisticsReporter
from scripts2.rag.file_persistence_manager import FilePersistenceManager

class MemoryModule(BaseModule):
    def __init__(self, base_path: str = ".", memory_enabled=True, response_generator: ResponseGeneratorModule = None):
        super().__init__("MemoryModule")
        self.memory_enabled = memory_enabled
        self.response_generator = response_generator
        self._last_memory_snapshot = None

        self.queue = asyncio.Queue()
        self.loop = None

        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)

        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.base_path / "memories" / "chroma.db"),
            settings=Settings(
                anonymized_telemetry=False,
                chroma_server_host=None,
                chroma_server_http_port=None
            )
        )

        # Initialize managers
        self.memory_storage = MemoryStorage(base_path)
        self.user_profile_manager = UserProfileManager(str(self.base_path / "memories" / "user_profiles.db"))
        self.chat_history_manager = ChatHistoryManager(self.chroma_client, "conversation_collection", "reflections_collection")
        self.memory_lifecycle_manager = MemoryLifecycleManager(self.memory_storage, self.chat_history_manager.conversation_collection)
        self.reflection_generator = ReflectionGenerator(self.chat_history_manager, self.response_generator, 20)
        self.memory_context_provider = MemoryContextProvider(self.memory_storage, self.chat_history_manager, self.reflection_generator, self.user_profile_manager)
        self.statistics_reporter = StatisticsReporter(self.memory_storage, self.user_profile_manager, self.chat_history_manager)
        self.file_persistence_manager = FilePersistenceManager(base_path)

        self.reflection_threshold = 20
        self.message_counter = 0
        self._pending_conversation_items = []
        self.consolidation_threshold = 10
        self.decay_threshold = 0.3

        print(f"[UserProfileManager] Thread ID for DB: {threading.get_ident()}")

        self.logger.info(f"ChromaDB initialized with {self.chat_history_manager.collection.count()} reflection memories")
        self.logger.info(f"MemoryModule initialized with {len(self.memory_storage.memories)} memories")


    async def start(self):
        if not self.memory_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.loop = asyncio.get_running_loop()
        await super().start()
        
    async def run(self):
        self.logger.info("[run] MemoryManager loop started.")

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
                        self._cleanup_old_memories()
                        next_cleanup = asyncio.create_task(self._schedule_cleanup(cleanup_interval))
                    elif task is queue_get_task:
                        message = task.result()
                        await self._handle_memory_event(message)
                        self.queue.task_done()

            except Exception as e:
                self.logger.error(f"[run] Error in loop: {e}")

           



    # === CORE MEMORY OPERATIONS ===
    def store_memory(self, content: str, memory_type: str = "semantic",
                     user_id: str = None, importance: float = 1.0,
                     tags: List[str] = None, metadata: Dict = None) -> str:
        """Store a semantic memory in the system (episodic memories now use conversation_collection)."""
        memory_id = self.memory_storage.store_memory(content, memory_type, user_id, importance, tags, metadata)

        if user_id:
            self.user_profile_manager._update_user_profile(user_id, content, memory_type)

        if len(self.memory_storage.memories) % self.consolidation_threshold == 0:
            self.memory_lifecycle_manager._consolidate_memories()

        self.logger.debug(f"Stored {memory_type} memory: {memory_id}")
        return memory_id

    def retrieve_memories(self, query: str = None, user_id: str = None,
                          memory_type: str = None, limit: int = 10,
                          min_relevance: float = 0.0) -> List[Memory]:
        """Retrieve semantic/procedural memories from JSON storage (conversations use conversation_collection)."""
        return self.memory_storage.retrieve_memories(query, user_id, memory_type, limit, min_relevance)

    # === REFLECTION SYSTEM (Generative Agents Technique) ===
    async def _perform_reflection(self) -> None:
        """Perform reflection on recent messages to generate Q&A memories."""
        self.logger.info("[Reflection] Starting reflection process...")

        if not self.response_generator:
            self.logger.warning("No response generator available for reflection")
            return

        qa_pairs = await self.reflection_generator._perform_reflection()

        if not qa_pairs:
            self.logger.info("[Reflection] No Q&A pairs generated")
            return

        self.logger.info(f"[Reflection] Successfully generated {len(qa_pairs)} Q&A pairs from reflection response")

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




    # === CHAT HISTORY MANAGEMENT ===

    def get_recent_chat_history(self, limit: int = 20) -> List[Dict]:
        """Get recent chat history from ChromaDB conversation collection."""
        return self.chat_history_manager.get_recent_chat_history(limit)

    def get_user_chat_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get chat history for a specific user from ChromaDB."""
        return self.chat_history_manager.get_user_chat_history(user_id, limit)

    # === COMPATIBILITY INTERFACE ===
    def add_conversation_item(self, role: str, content: str, user_id: str = None,
                         metadata: Dict = None) -> None:
        """Add a chat message to conversation collection with 1-minute decay."""
        self.chat_history_manager.add_conversation_item_sync(role, content, user_id, metadata)

        self.message_counter += 1
        if self.message_counter >= self.reflection_threshold:
            self.logger.info(f"[Reflection] Triggering reflection after {self.message_counter} messages (threshold: {self.reflection_threshold})")
            asyncio.create_task(self._perform_reflection())

    def get_memory_context(self, user_id: str = None, current_topic: str = None) -> str:
        """Generate memory context for prompts (enhanced version)."""
        return self.memory_context_provider.get_memory_context(user_id, current_topic)

    def update_user_profile(self, user_id: str,
                            personality_trait: str = None, preference: Dict = None,
                            last_seen: str = None) -> None:
        """Update user profile (compatibility method)."""
        self.user_profile_manager.update_user_profile(user_id, personality_trait, preference, last_seen)

        if personality_trait:
            self.store_memory(
                f"User {user_id} shows personality trait: {personality_trait}",
                "semantic",
                user_id,
                0.7,
                ["personality", personality_trait]
            )

    def get_user_profile(self, user_id: str) -> Dict:
        """Get user profile (compatibility method)."""
        return self.user_profile_manager.get_user_profile(user_id)

    def get_memory_stats(self) -> Dict:
        """Get memory system statistics."""
        return self.statistics_reporter.get_memory_stats()


    def _cleanup_old_memories(self) -> None:
        """Clean up old and decayed memories."""
        self.memory_lifecycle_manager.decay_old_memories()
        self.memory_lifecycle_manager.decay_chat_memories()

        self.logger.info("Memory cleanup completed")

    async def _detect_personality_traits(self, content: str) -> List[str]:
        """Detect personality traits using LLM analysis."""
        if not self.response_generator:
            self.logger.warning("No response generator available for personality trait detection")
            return []

        prompt = f"""Analyze the following user message and detect personality traits. Respond with a JSON object containing a "traits" array of detected traits (e.g., sarcastic, humorous, aggressive, polite, rude, enthusiastic, etc.). Only include traits that are clearly evident.

Message: "{content}"

Respond only with the JSON object, no additional text."""

        try:
            response = await self.response_generator._generate_response(prompt, use_system_prompt=False, max_new_tokens=100)
            response = response.strip()

            import json
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                traits = data.get('traits', [])
                if isinstance(traits, list):
                    return traits
                else:
                    self.logger.warning(f"Traits not a list: {traits}")
                    return []
            else:
                self.logger.warning(f"No JSON found in response: {response}")
                return []
        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"Error parsing personality traits response: {e}")
            return []

    async def _schedule_cleanup(self, delay: int):
        await asyncio.sleep(delay)

    async def _handle_memory_event(self, data: Dict):
        self.chat_history_manager.add_conversation_item_sync(**data)
        if data.get('user_id'):
            self.update_user_profile(data['user_id'], last_seen=datetime.now().isoformat())
           
            if data.get('role') == 'user' and data.get('content'):
                detected_traits = await self._detect_personality_traits(data['content'])
                for trait in detected_traits:
                    self.update_user_profile(data['user_id'], personality_trait=trait)
        self.message_counter += 1

        self.update_memories_if_changed()

        if self.message_counter >= self.reflection_threshold:
            self.logger.info(f"[Reflection] Triggering after {self.message_counter} messages")
            asyncio.create_task(self._perform_reflection())

    def submit_spoken_memory(self, role: str, content: str, user_id: str = None, metadata: Dict = None):
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
            self.logger.warning("submit_chat called before loop is set.")

    def queue_user_message(self, content, user_id=None, metadata=None):
        self._pending_conversation_items.append({
            "role": "user",
            "content": content,
            "user_id": user_id,
            "metadata": metadata or {}
        })

    def save_conversation_turn(self, assistant_content, assistant_metadata=None):
        for msg in self._pending_conversation_items:
            self.add_conversation_item(**msg)
        self._pending_conversation_items.clear()

        self.add_conversation_item(
            role="assistant",
            content=assistant_content,
            user_id="ai",
            metadata=assistant_metadata or {}
        )

    def get_recent_reflections(self, limit: int = 20) -> List[Dict]:
        """Get recent reflections from ChromaDB collection."""
        return self.chat_history_manager.get_recent_reflections(limit)

    def get_recent_memories(self, limit_chat: int = 20, limit_reflections: int = 20) -> Dict[str, List[Dict]]:
        """Get recent chat history and reflections combined."""
        return self.chat_history_manager.get_recent_memories(limit_chat, limit_reflections)
    
    def update_memories_if_changed(self):
        current_snapshot = self.get_recent_memories()

        snapshot_id = str(current_snapshot)

        if snapshot_id != self._last_memory_snapshot:
            self._last_memory_snapshot = snapshot_id
            self.event_broker.publish_event({
                "type": "memories_updated",
                "data": current_snapshot
            })

    async def stop(self):
        await super().stop()