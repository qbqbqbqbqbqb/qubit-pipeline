from datetime import datetime, timedelta
import time
from typing import List

from scripts2.modules.base_module import BaseModule
from scripts2.rag.memory_storage import MemoryStorage
from scripts2.core.memory import Memory


"""
Memory Lifecycle Manager Module

This module provides functionality to manage the lifecycle of memories in a Retrieval-Augmented Generation (RAG) system.
It handles memory consolidation, decay of old or irrelevant memories, and maintenance of memory storage integrity.
The MemoryLifecycleManager class orchestrates these processes to ensure efficient memory management and prevent
redundancy while maintaining relevance over time.
"""

class MemoryLifecycleManager(BaseModule):
    """
    Manages the lifecycle of memories in the system, including consolidation and decay processes.

    This class handles automated maintenance of memory storage to prevent redundancy,
    apply decay to irrelevant memories, and ensure efficient retrieval. It integrates with
    memory storage and conversation collections to maintain system performance.

    Attributes:
        memory_storage (MemoryStorage): The storage interface for memories.
        conversation_collection: The collection for conversation data (e.g., ChromaDB collection).
        decay_threshold (float): Threshold below which memories are decayed (default: 0.3).
        consolidation_threshold (int): Minimum number of memories to trigger consolidation (default: 10).
    """

    def __init__(self, memory_storage: MemoryStorage, conversation_collection, decay_threshold: float = 0.3, consolidation_threshold: int = 10):
        """
        Initialize the MemoryLifecycleManager.

        Args:
            memory_storage (MemoryStorage): The storage system for memories.
            conversation_collection: The collection handling conversation data.
            decay_threshold (float, optional): Threshold for memory decay (default: 0.3).
            consolidation_threshold (int, optional): Threshold for memory consolidation (default: 10).
        """
        super().__init__("MemoryLifecycleManager")
        self.memory_storage = memory_storage
        self.conversation_collection = conversation_collection
        self.decay_threshold = decay_threshold
        self.consolidation_threshold = consolidation_threshold

    def _consolidate_memories(self):
        """
        Consolidate related memories to prevent redundancy.

        Groups memories by user and consolidates those with more than 5 entries per user.
        This method helps maintain memory efficiency by summarizing redundant or related memories.
        """
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
        """
        Consolidate memories for a specific user.

        Filters recent memories (within last 24 hours) and creates a summary if there are more than 3.
        The summary is stored as a new semantic memory with tags for identification.

        Args:
            user_id (str): The ID of the user whose memories are being consolidated.
            memories (List[Memory]): List of memories associated with the user.
        """
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
        """
        Generate a summary of related memories by concatenating their contents.

        Takes the last 5 memories and joins the first 3 contents with ' | ' separator.

        Args:
            memories (List[Memory]): List of memories to summarize.

        Returns:
            str: A concatenated summary string of memory contents, or empty string if no contents.
        """
        contents = [m.content for m in memories[-5:]]
        if contents:
            return " | ".join(contents[:3])
        return ""

    def decay_old_memories(self):
        """
        Apply decay to old, irrelevant memories based on decay factor thresholds.

        Memories with decay factor below the decay_threshold are removed entirely.
        Memories with decay factor between decay_threshold and 0.8 have their importance reduced by 10%.
        Reflections are skipped from decay. Removed memories are also deleted from semantic index and filesystem.

        Logs the decay actions for monitoring.
        """
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
        """
        Remove a memory from the semantic index.

        Extracts keywords from the memory content (words longer than 3 characters) and removes
        the memory ID from the corresponding keyword entries in the semantic index.
        Cleans up empty keyword entries.

        Args:
            memory (Memory): The memory to remove from the index.
        """
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword in self.memory_storage.semantic_index and memory.id in self.memory_storage.semantic_index[keyword]:
                self.memory_storage.semantic_index[keyword].remove(memory.id)
                if not self.memory_storage.semantic_index[keyword]:
                    del self.memory_storage.semantic_index[keyword]

    def decay_chat_memories(self):
        """
        Apply rapid decay to chat memories in conversation collections with a 1-minute lifetime.

        Queries the conversation collection for entries older than 1 minute and deletes them.
        Handles both ISO timestamp strings and Unix timestamps. Logs decayed entries and
        total count for monitoring. Errors during logging are debugged without failing the process.

        This ensures temporary chat data does not accumulate indefinitely.
        """
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