"""
Module for persistent storage and retrieval of memory objects.

This module provides the MemoryStorage class for managing memory objects,
including storing them to disk in JSON format, retrieving them based on queries,
and maintaining a semantic index for efficient retrieval.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from scripts2.core.memory import Memory


class MemoryStorage:
    """
    A class for storing and retrieving memory objects persistently.

    This class handles the persistence layer for memories, using JSON files for storage
    and maintaining an in-memory semantic index for query-based retrieval. It supports
    different memory types, user-specific filtering, and relevance-based ranking.

    Attributes:
        base_path (Path): The base directory path for storage.
        memories_dir (Path): Directory where memory JSON files are stored.
        memories (Dict[str, Memory]): In-memory dictionary of loaded memories keyed by ID.
        semantic_index (Dict[str, List[str]]): Index mapping keywords to memory IDs.
    """
    def __init__(self, base_path: str = "."):
        """
        Initialize the MemoryStorage instance.

        Sets up the storage directories and loads existing memories from disk.

        Args:
            base_path (str): The base directory path for storing memories. Defaults to current directory.
        """
        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)

        self.memories: Dict[str, Memory] = {}
        self.semantic_index: Dict[str, List[str]] = {}

        self._load_memories()

    def _load_memories(self):
        """
        Load all memories from storage.

        Scans the memories directory for JSON files, loads each memory object,
        and updates the in-memory storage and semantic index.
        """
        memory_files = list(self.memories_dir.glob("*.json"))
        for file_path in memory_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    memory = Memory.from_dict(data)
                    self.memories[memory.id] = memory
                    self._update_semantic_index(memory)
            except Exception as e:
                pass

    def _update_semantic_index(self, memory: Memory):
        """
        Update the semantic index with keywords from a memory.

        Extracts keywords from the memory content and adds the memory ID to the index
        for each keyword.

        Args:
            memory (Memory): The memory object to index.
        """
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword not in self.semantic_index:
                self.semantic_index[keyword] = []
            if memory.id not in self.semantic_index[keyword]:
                self.semantic_index[keyword].append(memory.id)

    def _save_memory(self, memory: Memory):
        """
        Save a single memory to file.

        Serializes the memory object to JSON and writes it to a file named after the memory ID.

        Args:
            memory (Memory): The memory object to save.
        """
        file_path = self.memories_dir / f"{memory.id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass

    def _save_json(self, file_path: Path, data: Any) -> None:
        """
        Save data to JSON file.

        Generic method to save arbitrary data to a JSON file with proper encoding.

        Args:
            file_path (Path): The file path to save to.
            data (Any): The data to serialize and save.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            pass

    def store_memory(self, content: str, memory_type: str = "semantic",
                      user_id: str = None, importance: float = 1.0,
                      tags: List[str] = None, metadata: Dict = None) -> str:
        """
        Store a new memory in the system.

        Creates a new Memory object, adds it to in-memory storage, updates the semantic index,
        and persists it to disk.

        Args:
            content (str): The content of the memory.
            memory_type (str): The type of memory. Defaults to "semantic".
            user_id (str): The user ID associated with the memory. Defaults to None.
            importance (float): The importance score of the memory. Defaults to 1.0.
            tags (List[str]): List of tags for the memory. Defaults to None.
            metadata (Dict): Additional metadata for the memory. Defaults to None.

        Returns:
            str: The ID of the newly stored memory.
        """
        memory = Memory(content, memory_type, user_id, importance, tags, metadata)
        self.memories[memory.id] = memory

        self._update_semantic_index(memory)
        self._save_memory(memory)

        return memory.id

    def retrieve_memories(self, query: str = None, user_id: str = None,
                          memory_type: str = None, limit: int = 10,
                          min_relevance: float = 0.0) -> List[Memory]:
        """
        Retrieve memories based on query parameters.

        Filters memories by user, type, and query relevance, ranks them by relevance,
        importance, and recency, and updates access times for retrieved memories.

        Args:
            query (str): The search query for semantic matching. Defaults to None.
            user_id (str): Filter by user ID. Defaults to None.
            memory_type (str): Filter by memory type. Defaults to None.
            limit (int): Maximum number of memories to return. Defaults to 10.
            min_relevance (float): Minimum relevance score for query matches. Defaults to 0.0.

        Returns:
            List[Memory]: List of retrieved and ranked memory objects.
        """
        candidates = list(self.memories.values())

        if user_id:
            candidates = [m for m in candidates if m.user_id == user_id]

        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]

        if query:
            candidates = self._rank_memories_by_relevance(candidates, query)

        if query:
            candidates = [m for m in candidates if m.relevance_score >= min_relevance]

        candidates.sort(key=lambda m: (
            m.relevance_score,
            m.importance,
            m.last_accessed
        ), reverse=True)

        for memory in candidates[:limit]:
            memory.update_access()
            self._save_memory(memory)

        return candidates[:limit]

    def _rank_memories_by_relevance(self, memories: List[Memory], query: str) -> List[Memory]:
        """
        Rank memories by semantic relevance to the query.

        Calculates relevance based on word overlap between query and memory content,
        boosted by importance and recency.

        Args:
            memories (List[Memory]): List of memories to rank.
            query (str): The search query.

        Returns:
            List[Memory]: The list of memories with relevance scores set.
        """
        query_words = set(query.lower().split())
        scored_memories = []

        for memory in memories:
            memory_words = set(memory.content.lower().split())
            overlap = len(query_words.intersection(memory_words))

            total_words = len(query_words.union(memory_words))

            if total_words > 0:
                relevance = overlap / total_words
            else:
                relevance = 0.0

            recency_boost = min(1.0, (datetime.now() - memory.created_at).days / 7.0)
            relevance *= (1.0 + memory.importance) * (1.0 + recency_boost)

            memory.relevance_score = relevance
            scored_memories.append(memory)

        return scored_memories