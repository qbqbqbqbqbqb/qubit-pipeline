import json
import os
import hashlib
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np

from scripts.utils.log_utils import get_logger

logger = get_logger("MemoryManager")

class Memory:
    """Individual memory unit with metadata."""

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

class MemoryManager:
    """
    Advanced memory system for VTuber AI bot.
    Features episodic, semantic, and procedural memory with intelligent retrieval.
    """

    def __init__(self, base_path: str = ".", response_generator=None):
        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)
        self.response_generator = response_generator

        self.memories: Dict[str, Memory] = {}
        self.user_profiles: Dict[str, Dict] = {}
        self.semantic_index: Dict[str, List[str]] = {}

        self.chat_history: List[Dict] = []
        self.chat_history_file = self.base_path / "chat_history.json"
        self.max_chat_history = 100

        self.max_memories = 5000
        self.consolidation_threshold = 10
        self.decay_threshold = 0.3

        self.reflection_threshold = 20
        self.message_counter = 0
        self.reflection_prompt = """
Given the following recent conversation messages, generate 3 high-level question-answer pairs that capture the most important and distinctive aspects of this conversation. Focus on insights, patterns, or key information that would be valuable to remember for future interactions.

Recent conversation:
{recent_messages}

Please format your response as exactly 3 question-answer pairs in this format:
Q1: [Question]
A1: [Answer]

Q2: [Question]
A2: [Answer]

Q3: [Question]
A3: [Answer]
"""

        self._load_memories()
        self._load_user_profiles()
        self._load_chat_history()

        logger.info(f"MemoryManager initialized with {len(self.memories)} memories")

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
                logger.error(f"Error loading memory from {file_path}: {e}")

    def _load_user_profiles(self):
        """Load user profiles."""
        profile_file = self.base_path / "user_profiles.json"
        try:
            if profile_file.exists():
                with open(profile_file, 'r', encoding='utf-8') as f:
                    self.user_profiles = json.load(f)
        except Exception as e:
            logger.error(f"Error loading user profiles: {e}")
            self.user_profiles = {}

    def _load_chat_history(self):
        """Load chat history."""
        try:
            if self.chat_history_file.exists():
                with open(self.chat_history_file, 'r', encoding='utf-8') as f:
                    self.chat_history = json.load(f)
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            self.chat_history = []

    def _save_memory(self, memory: Memory):
        """Save a single memory to file."""
        file_path = self.memories_dir / f"{memory.id}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving memory {memory.id}: {e}")

    def _save_user_profiles(self):
        """Save user profiles."""
        profile_file = self.base_path / "user_profiles.json"
        try:
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_profiles, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user profiles: {e}")

    def _update_semantic_index(self, memory: Memory):
        """Update semantic index with memory keywords."""
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword not in self.semantic_index:
                self.semantic_index[keyword] = []
            if memory.id not in self.semantic_index[keyword]:
                self.semantic_index[keyword].append(memory.id)

    def _save_json(self, file_path: Path, data: Any) -> None:
        """Save data to JSON file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")

    # === CORE MEMORY OPERATIONS ===
    def store_memory(self, content: str, memory_type: str = "episodic",
                    user_id: str = None, importance: float = 1.0,
                    tags: List[str] = None, metadata: Dict = None) -> str:
        """Store a new memory in the system."""
        memory = Memory(content, memory_type, user_id, importance, tags, metadata)
        self.memories[memory.id] = memory
        self._update_semantic_index(memory)
        self._save_memory(memory)

        if user_id:
            self._update_user_profile(user_id, memory)

        if len(self.memories) % self.consolidation_threshold == 0:
            self._consolidate_memories()

        logger.debug(f"Stored {memory_type} memory: {memory.id}")
        return memory.id

    def retrieve_memories(self, query: str = None, user_id: str = None,
                         memory_type: str = None, limit: int = 10,
                         min_relevance: float = 0.0) -> List[Memory]:
        """Retrieve memories based on various criteria."""
        candidates = list(self.memories.values())

        if user_id:
            candidates = [m for m in candidates if m.user_id == user_id]

        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]

        if query:
            candidates = self._rank_memories_by_relevance(candidates, query)

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

    def _update_user_profile(self, user_id: str, memory: Memory):
        """Update user profile based on memory."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "user_id": user_id,
                "first_seen": datetime.now().isoformat(),
                "total_memories": 0,
                "personality_vector": {},
                "interaction_patterns": {},
                "relationship_score": 0.0
            }

        profile = self.user_profiles[user_id]
        profile["last_seen"] = datetime.now().isoformat()
        profile["total_memories"] += 1

        if memory.memory_type == "episodic":
            emotional_words = {
                "happy": 0.8, "excited": 0.7, "love": 0.9,
                "sad": -0.6, "angry": -0.8, "hate": -0.9
            }

            for word, valence in emotional_words.items():
                if word in memory.content.lower():
                    memory.emotional_valence = valence
                    profile["relationship_score"] += valence * 0.1
                    break

        self._save_user_profiles()

    def _consolidate_memories(self):
        """Consolidate related memories to prevent redundancy."""
        user_memories = {}
        for memory in self.memories.values():
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
                summary_memory = Memory(
                    content=f"Summary of recent interactions with {user_id}: {summary_content}",
                    memory_type="semantic",
                    user_id=user_id,
                    importance=2.0,
                    tags=["summary", "consolidated"]
                )
                self.store_memory(summary_memory.content, "semantic", user_id, 2.0, ["summary"])

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

        for memory in self.memories.values():
            if "reflection" in memory.tags:
                continue

            decay_factor = memory.calculate_decay_factor()

            if decay_factor < self.decay_threshold:
                memories_to_decay.append(memory.id)
            elif decay_factor < 0.8:
                memory.importance *= 0.9 

        for memory_id in memories_to_decay:
            if memory_id in self.memories:
                memory = self.memories[memory_id]
                logger.info(f"Decaying memory: {memory.content[:50]}...")
                del self.memories[memory_id]

                self._remove_from_semantic_index(memory)

                file_path = self.memories_dir / f"{memory_id}.json"
                if file_path.exists():
                    file_path.unlink()

        if memories_to_decay:
            logger.info(f"Decayed {len(memories_to_decay)} old memories")

    def decay_chat_memories(self):
        """Apply rapid decay to chat memories (1 minute lifetime)."""
        memories_to_decay = []
        current_time = datetime.now()
        one_minute_ago = current_time - timedelta(minutes=1)

        for memory in self.memories.values():
            if memory.memory_type == "episodic" and memory.created_at < one_minute_ago:
                if memory.access_count == 0 and memory.importance <= 1.0:
                    memories_to_decay.append(memory.id)

        for memory_id in memories_to_decay:
            if memory_id in self.memories:
                memory = self.memories[memory_id]
                logger.debug(f"Decaying chat memory (1min): {memory.content[:50]}...")
                del self.memories[memory_id]

                self._remove_from_semantic_index(memory)

                file_path = self.memories_dir / f"{memory_id}.json"
                if file_path.exists():
                    file_path.unlink()

        if memories_to_decay:
            logger.debug(f"Decayed {len(memories_to_decay)} chat memories (1 minute lifetime)")

    # === REFLECTION SYSTEM (Generative Agents Technique) ===
    async def _perform_reflection(self) -> None:
        """Perform reflection on recent messages to generate Q&A memories."""
        if not self.response_generator:
            logger.warning("No response generator available for reflection")
            return

        recent_messages = self.get_recent_chat_history(limit=self.reflection_threshold)
        if len(recent_messages) < 10: 
            return

        formatted_messages = []
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            user_id = msg.get("user_id", "unknown")
            if role == "user":
                formatted_messages.append(f"User {user_id}: {content}")
            else:
                formatted_messages.append(f"Assistant: {content}")

        messages_text = "\n".join(formatted_messages)

        reflection_messages = [
            {"role": "system", "content": "You are an AI assistant that analyzes conversations and creates insightful question-answer pairs."},
            {"role": "user", "content": self.reflection_prompt.format(recent_messages=messages_text)}
        ]

        try:
            reflection_response = await self.response_generator.generate_response_safely(reflection_messages)
            logger.info(f"Generated reflection: {reflection_response[:100]}...")

            qa_pairs = self._parse_qa_pairs(reflection_response)

            for i, (question, answer) in enumerate(qa_pairs, 1):
                qa_memory = f"Q: {question}\nA: {answer}"
                self.store_memory(
                    content=qa_memory,
                    memory_type="semantic",
                    importance=2.5,
                    tags=["reflection", "qa", f"reflection_{i}"],
                    metadata={"type": "short-term", "reflection_batch": self.message_counter}
                )
                logger.info(f"Stored reflection memory Q{i}: {question[:50]}...")

            self.message_counter = 0

        except Exception as e:
            logger.error(f"Error during reflection: {e}")

    def _parse_qa_pairs(self, response: str) -> List[Tuple[str, str]]:
        """Parse Q&A pairs from LLM reflection response."""
        qa_pairs = []

        qa_pattern = r'Q(\d+):\s*(.*?)\nA(\d+):\s*(.*?)(?=\nQ\d+:|$)'
        matches = re.findall(qa_pattern, response, re.DOTALL)

        for match in matches:
            q_num, question, a_num, answer = match
            if q_num == a_num:
                qa_pairs.append((question.strip(), answer.strip()))

        if not qa_pairs:
            lines = response.strip().split('\n')
            current_q = None
            current_a = None

            for line in lines:
                line = line.strip()
                if line.startswith('Q') and ':' in line:
                    if current_q and current_a:
                        qa_pairs.append((current_q, current_a))
                    current_q = line.split(':', 1)[1].strip()
                    current_a = None
                elif line.startswith('A') and ':' in line and current_q:
                    current_a = line.split(':', 1)[1].strip()

            if current_q and current_a:
                qa_pairs.append((current_q, current_a))

        return qa_pairs[:3]

    def _remove_from_semantic_index(self, memory: Memory):
        """Remove memory from semantic index."""
        words = memory.content.lower().split()
        keywords = [word for word in words if len(word) > 3]

        for keyword in set(keywords):
            if keyword in self.semantic_index and memory.id in self.semantic_index[keyword]:
                self.semantic_index[keyword].remove(memory.id)
                if not self.semantic_index[keyword]:
                    del self.semantic_index[keyword]


    # === CHAT HISTORY MANAGEMENT ===
    def add_chat_message_sync(self, role: str, content: str, user_id: str = None,
                             metadata: Dict = None) -> None:
        """Add a chat message to persistent history (synchronous version)."""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "user_id": user_id,
            "metadata": metadata or {}
        }

        self.chat_history.append(message)

        if len(self.chat_history) > self.max_chat_history:
            self.chat_history = self.chat_history[-self.max_chat_history:]

        self._save_chat_history()

        self.message_counter += 1
        if self.message_counter >= self.reflection_threshold:
            asyncio.create_task(self._perform_reflection())

    def get_recent_chat_history(self, limit: int = 20) -> List[Dict]:
        """Get recent chat history."""
        return self.chat_history[-limit:]

    def get_user_chat_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get chat history for a specific user."""
        user_messages = [msg for msg in self.chat_history if msg.get("user_id") == user_id]
        return user_messages[-limit:]

    def _save_chat_history(self) -> None:
        """Save chat history."""
        self._save_json(self.chat_history_file, self.chat_history)

    # === COMPATIBILITY INTERFACE ===
    def add_chat_message(self, role: str, content: str, user_id: str = None,
                        metadata: Dict = None) -> None:
        """Add a chat message (main synchronous method with async reflection)."""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "user_id": user_id,
            "metadata": metadata or {}
        }

        self.chat_history.append(message)

        if len(self.chat_history) > self.max_chat_history:
            self.chat_history = self.chat_history[-self.max_chat_history:]

        self._save_chat_history()

        memory_type = "episodic"
        if role == "assistant":
            memory_type = "episodic"

        importance = 1.0
        if metadata and metadata.get("type") == "monologue":
            importance = 0.8 

        tags = []
        if metadata:
            if metadata.get("type") == "monologue":
                tags.append("monologue")
            tags.extend(metadata.get("tags", []))

        self.store_memory(content, memory_type, user_id, importance, tags, metadata)

        self.message_counter += 1
        if self.message_counter >= self.reflection_threshold:
            asyncio.create_task(self._perform_reflection())

    def get_memory_context(self, user_id: str = None, current_topic: str = None) -> str:
        """Generate memory context for prompts (enhanced version)."""
        context_parts = []

        if user_id:
            user_memories = self.retrieve_memories(
                user_id=user_id,
                memory_type="episodic",
                limit=3
            )
            if user_memories:
                memory_texts = [m.content for m in user_memories]
                context_parts.append(f"About user {user_id}: {'; '.join(memory_texts)}")

        if current_topic:
            topic_memories = self.retrieve_memories(
                query=current_topic,
                limit=2,
                min_relevance=0.1
            )
            if topic_memories:
                memory_texts = [m.content for m in topic_memories]
                context_parts.append(f"Relevant context: {'; '.join(memory_texts)}")

        recent_memories = self.retrieve_memories(
            memory_type="episodic",
            limit=2
        )
        if recent_memories:
            memory_texts = [m.content for m in recent_memories]
            context_parts.append(f"Recent activity: {'; '.join(memory_texts)}")

        return "\n".join(context_parts) if context_parts else ""

    def update_user_profile(self, user_id: str, username: str = None,
                          personality_trait: str = None, preference: Dict = None) -> None:
        """Update user profile (compatibility method)."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "user_id": user_id,
                "first_seen": datetime.now().isoformat(),
                "total_memories": 0,
                "personality_vector": {},
                "interaction_patterns": {},
                "relationship_score": 0.0
            }

        profile = self.user_profiles[user_id]

        if username:
            profile["username"] = username

        profile["last_seen"] = datetime.now().isoformat()

        if personality_trait:
            self.store_memory(
                f"User {user_id} shows personality trait: {personality_trait}",
                "semantic",
                user_id,
                0.7,
                ["personality", personality_trait]
            )

        if preference:
            profile["preferences"] = profile.get("preferences", {})
            profile["preferences"].update(preference)

        self._save_user_profiles()

    def get_user_profile(self, user_id: str) -> Dict:
        """Get user profile (compatibility method)."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "user_id": user_id,
                "first_seen": datetime.now().isoformat(),
                "total_memories": 0,
                "personality_vector": {},
                "interaction_patterns": {},
                "relationship_score": 0.0
            }
            self._save_user_profiles()

        return self.user_profiles[user_id]

    def get_memory_stats(self) -> Dict:
        """Get memory system statistics."""
        memory_types = {}
        for memory in self.memories.values():
            memory_types[memory.memory_type] = memory_types.get(memory.memory_type, 0) + 1

        return {
            "total_memories": len(self.memories),
            "memory_types": memory_types,
            "users": len(self.user_profiles),
            "semantic_index_size": len(self.semantic_index),
            "oldest_memory": min((m.created_at for m in self.memories.values()), default=None),
            "newest_memory": max((m.created_at for m in self.memories.values()), default=None)
        }


    def cleanup_old_memories(self) -> None:
        """Clean up old and decayed memories."""
        self.decay_old_memories()
        self.decay_chat_memories()
        logger.info("Memory cleanup completed")