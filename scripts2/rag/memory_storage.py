import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from scripts2.core.memory import Memory


class MemoryStorage:
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)

        self.memories: Dict[str, Memory] = {}
        self.semantic_index: Dict[str, List[str]] = {}

        self._load_memories()

    def _load_memories(self):
        """Load all memories from storage."""
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
        """Update semantic index with memory keywords."""
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword not in self.semantic_index:
                self.semantic_index[keyword] = []
            if memory.id not in self.semantic_index[keyword]:
                self.semantic_index[keyword].append(memory.id)

    def _save_memory(self, memory: Memory):
        """Save a single memory to file."""
        file_path = self.memories_dir / f"{memory.id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass

    def _save_json(self, file_path: Path, data: Any) -> None:
        """Save data to JSON file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            pass

    def store_memory(self, content: str, memory_type: str = "semantic",
                     user_id: str = None, importance: float = 1.0,
                     tags: List[str] = None, metadata: Dict = None) -> str:
        """Store a semantic memory in the system."""
        memory = Memory(content, memory_type, user_id, importance, tags, metadata)
        self.memories[memory.id] = memory

        self._update_semantic_index(memory)
        self._save_memory(memory)

        return memory.id

    def retrieve_memories(self, query: str = None, user_id: str = None,
                          memory_type: str = None, limit: int = 10,
                          min_relevance: float = 0.0) -> List[Memory]:
        """Retrieve semantic/procedural memories from JSON storage."""
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
        """Rank memories by semantic relevance to query."""
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