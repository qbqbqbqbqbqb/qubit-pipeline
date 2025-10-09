from datetime import datetime
import hashlib
from typing import Dict, List

import numpy as np


class Memory:
    def __init__(self, content: str, memory_type: str = "episodic",
                 user_id: str = None, importance: float = 1.0,
                 tags: List[str] = None, metadata: Dict = None):
        self.id = hashlib.md5(f"{content}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
        self.content = content
        self.memory_type = memory_type 
        self.user_id = user_id
        self.importance = importance
        self.tags = tags or []
        self.metadata = metadata or {}

        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.access_count = 0

        self.relevance_score = 0.0
        self.emotional_valence = 0.0
        self.confidence = 1.0

        self.related_memories: List[str] = []

    def to_dict(self) -> Dict:
        """Convert memory to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "user_id": self.user_id,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
            "emotional_valence": self.emotional_valence,
            "confidence": self.confidence,
            "related_memories": self.related_memories
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Memory':
        """Create memory from dictionary."""
        memory = cls(
            content=data["content"],
            memory_type=data.get("memory_type", "episodic"),
            user_id=data.get("user_id"),
            importance=data.get("importance", 1.0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {})
        )
        memory.id = data["id"]
        memory.created_at = datetime.fromisoformat(data["created_at"])
        memory.last_accessed = datetime.fromisoformat(data["last_accessed"])
        memory.access_count = data.get("access_count", 0)
        memory.relevance_score = data.get("relevance_score", 0.0)
        memory.emotional_valence = data.get("emotional_valence", 0.0)
        memory.confidence = data.get("confidence", 1.0)
        memory.related_memories = data.get("related_memories", [])
        return memory

    def update_access(self):
        """Update access statistics."""
        self.last_accessed = datetime.now()
        self.access_count += 1

    def calculate_decay_factor(self) -> float:
        """Calculate decay factor based on age and access patterns."""
        age_days = (datetime.now() - self.created_at).days
        recency_factor = min(1.0, self.access_count / max(1, age_days))
        importance_factor = self.importance

        decay = np.exp(-age_days / 30.0) * (0.5 + 0.5 * recency_factor) * importance_factor
        return max(0.1, decay)