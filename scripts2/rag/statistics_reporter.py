from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from scripts2.modules.memory_storage import MemoryStorage
    from scripts2.modules.user_profile_manager import UserProfileManager
    from scripts2.modules.chat_history_manager import ChatHistoryManager

class StatisticsReporter:
    def __init__(self, memory_storage: 'MemoryStorage', user_profile_manager: 'UserProfileManager', chat_history_manager: 'ChatHistoryManager'):
        self.memory_storage = memory_storage
        self.user_profile_manager = user_profile_manager
        self.chat_history_manager = chat_history_manager

    def get_memory_stats(self) -> Dict:
        """
        Retrieve comprehensive statistics about the memory system and related data.

        This method aggregates various metrics from memory storage, user profiles,
        chat history collections, and semantic indexing. It handles potential
        exceptions when accessing external data sources like ChromaDB collections.

        Returns:
            Dict containing statistics with the following keys:
                - total_memories: Total number of memories in storage
                - chromadb_memories: Dict with conversation and reflection counts
                  - conversations: Number of conversation entries in ChromaDB
                  - reflections: Number of reflection entries in ChromaDB
                - memory_types: Dict mapping memory types to their counts
                - users: Number of user profiles
                - semantic_index_size: Size of the semantic index
                - oldest_memory: Timestamp of the oldest memory (or None if empty)
                - newest_memory: Timestamp of the newest memory (or None if empty)
        """
        memory_types = {}
        for memory in self.memory_storage.memories.values():
            memory_types[memory.memory_type] = memory_types.get(memory.memory_type, 0) + 1

        conversation_count = 0
        reflection_count = 0

        try:
            conversation_count = self.chat_history_manager.conversation_collection.count()
            reflection_count = self.chat_history_manager.collection.count()
        except Exception:
            pass

        return {
            "total_memories": len(self.memory_storage.memories),
            "chromadb_memories": {
                "conversations": conversation_count,
                "reflections": reflection_count
            },
            "memory_types": memory_types,
            "users": len(self.user_profile_manager.user_profiles),
            "semantic_index_size": len(self.memory_storage.semantic_index),
            "oldest_memory": min((m.created_at for m in self.memory_storage.memories.values()), default=None),
            "newest_memory": max((m.created_at for m in self.memory_storage.memories.values()), default=None)
        }