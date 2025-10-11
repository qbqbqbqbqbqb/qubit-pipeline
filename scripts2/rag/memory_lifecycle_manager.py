from datetime import datetime, timedelta
import time
from typing import List

from scripts2.modules.base_module import BaseModule
from scripts2.rag.memory_storage import MemoryStorage
from scripts2.core.memory import Memory


class MemoryLifecycleManager(BaseModule):
    def __init__(self, memory_storage: MemoryStorage, conversation_collection, decay_threshold: float = 0.3, consolidation_threshold: int = 10):
        super().__init__("MemoryLifecycleManager")
        self.memory_storage = memory_storage
        self.conversation_collection = conversation_collection
        self.decay_threshold = decay_threshold
        self.consolidation_threshold = consolidation_threshold

    def _consolidate_memories(self):
        """Consolidate related memories to prevent redundancy."""
        user_memories = {}
        for memory in self.memory_storage.memories.values():
            if memory.user_id:
                if memory.user_id not in user_memories:
                    user_memories[memory.user_id] = []
                user_memories[memory.user_id].append(memory)

        for user_id, memories in user_memories.items():
            if len(memories) > 5:
                self._consolidate_user_memories(user_id, memories)

    def _consolidate_user_memories(self, user_id: str, memories: List[Memory]):
        """Consolidate memories for a specific user."""
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_memories = [m for m in memories if m.created_at > recent_cutoff]

        if len(recent_memories) > 3:
            summary_content = self._generate_memory_summary(recent_memories)
            if summary_content:
                self.memory_storage.store_memory(
                    content=f"Summary of recent interactions with {user_id}: {summary_content}",
                    memory_type="semantic",
                    user_id=user_id,
                    importance=2.0,
                    tags=["summary", "consolidated"]
                )

    def _generate_memory_summary(self, memories: List[Memory]) -> str:
        """Generate a summary of related memories."""
        contents = [m.content for m in memories[-5:]]
        if contents:
            return " | ".join(contents[:3])
        return ""

    def decay_old_memories(self):
        """Apply decay to old, irrelevant memories."""
        memories_to_decay = []
        current_time = datetime.now()

        for memory in self.memory_storage.memories.values():
            if "reflection" in memory.tags:
                continue

            decay_factor = memory.calculate_decay_factor()

            if decay_factor < self.decay_threshold:
                memories_to_decay.append(memory.id)
            elif decay_factor < 0.8:
                memory.importance *= 0.9

        for memory_id in memories_to_decay:
            if memory_id in self.memory_storage.memories:
                memory = self.memory_storage.memories[memory_id]
                self.logger.info(f"Decaying memory: {memory.content[:50]}...")
                del self.memory_storage.memories[memory_id]

                self._remove_from_semantic_index(memory)

                file_path = self.memory_storage.memories_dir / f"{memory_id}.json"
                if file_path.exists():
                    file_path.unlink()

        if memories_to_decay:
            self.logger.info(f"Decayed {len(memories_to_decay)} old memories")

    def _remove_from_semantic_index(self, memory: Memory):
        """Remove memory from semantic index."""
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword in self.memory_storage.semantic_index and memory.id in self.memory_storage.semantic_index[keyword]:
                self.memory_storage.semantic_index[keyword].remove(memory.id)
                if not self.memory_storage.semantic_index[keyword]:
                    del self.memory_storage.semantic_index[keyword]

    def decay_chat_memories(self):
        """Apply rapid decay to chat memories and ChromaDB collections (1 minute lifetime)."""
        current_time = datetime.now()
        one_minute_ago = current_time - timedelta(minutes=1)
        one_minute_ago_timestamp = time.time() - 60

        try:
            conversation_results = self.conversation_collection.get()
            conversation_ids_to_delete = []

            for i, metadata in enumerate(conversation_results["metadatas"]):
                if metadata and "timestamp" in metadata:
                    entry_timestamp = metadata["timestamp"]
                    try:
                        if isinstance(entry_timestamp, str):
                            entry_time = datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00'))
                        else:
                            entry_time = datetime.fromtimestamp(entry_timestamp)

                        if entry_time < one_minute_ago:
                            conversation_ids_to_delete.append(conversation_results["ids"][i])
                    except:
                        if isinstance(entry_timestamp, (int, float)) and entry_timestamp < one_minute_ago_timestamp:
                            conversation_ids_to_delete.append(conversation_results["ids"][i])

            if conversation_ids_to_delete:
                for i, conv_id in enumerate(conversation_ids_to_delete):
                    try:
                        conv_results = self.conversation_collection.get(ids=[conv_id])
                        if conv_results["documents"]:
                            content = conv_results["documents"][0]
                            self.logger.info(f"[Conversation Decay] Removed old conversation: '{content[:100]}{'...' if len(content) > 100 else ''}' (ID: {conv_id})")
                    except Exception as e:
                        self.logger.debug(f"Could not log decayed conversation {conv_id}: {e}")

                self.conversation_collection.delete(conversation_ids_to_delete)
                self.logger.info(f"[Conversation Decay] Successfully decayed {len(conversation_ids_to_delete)} conversation entries (1 minute lifetime)")

        except Exception as e:
            self.logger.debug(f"Error cleaning conversation collection: {e}")