import json
import os
import hashlib
import asyncio
import re
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np

import chromadb
from chromadb.config import Settings

from scripts.utils.log_utils import get_logger

logger = get_logger("MemoryManager")

class Memory:
    """
    Represents an individual memory unit with rich metadata.

    This class encapsulates semantic memories that persist in JSON format.
    Each memory has content, type, user association, importance scoring,
    tags, and various metadata for retrieval and decay calculations.

    Attributes:
        id (str): Unique 8-character hash identifier
        content (str): The actual memory content/text
        memory_type (str): Type of memory ('semantic', 'procedural', etc.)
        user_id (str): Associated user ID, if any
        importance (float): Importance score (0.0-1.0, higher = more important)
        tags (List[str]): List of tag strings for categorization
        metadata (Dict): Additional metadata dictionary
        created_at (datetime): When memory was created
        last_accessed (datetime): When memory was last retrieved
        access_count (int): Number of times memory has been accessed
        relevance_score (float): Computed relevance score for queries
        emotional_valence (float): Emotional sentiment score
        confidence (float): Confidence in memory accuracy
        related_memories (List[str]): IDs of related memories
    """

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
    Simplified memory management system for VTuber AI bot.

    This system maintains two types of storage:
    - ChromaDB: Fast, vector-based storage for conversations (with 1-minute decay)
      and AI-generated reflections (persistent)
    - JSON files: Structured storage for semantic memories and user profiles

    Key Components:
    - conversation_collection: Chat messages and monologues (1-minute decay)
    - reflections_collection: AI insights and learned patterns (persistent)
    - user_profiles.json: User interaction data and personality tracking
    - semantic memories: Long-term knowledge stored as JSON files

    The system automatically cleans up old conversations while preserving
    valuable semantic knowledge and user relationship data.
    """

    def __init__(self, base_path: str = ".", response_generator=None):
        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)
        self.response_generator = response_generator

        self.chroma_client = chromadb.PersistentClient(
            path=str(self.base_path / "memories" / "chroma.db"),
            settings=Settings(
                anonymized_telemetry=False,
                chroma_server_host=None,
                chroma_server_http_port=None
            )
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="reflections_collection",
            metadata={"hnsw:space": "cosine"}
        )

        self.conversation_collection = self.chroma_client.get_or_create_collection(
            name="conversation_collection",
            metadata={"hnsw:space": "l2"}
        )



        logger.info(f"ChromaDB initialized with {self.collection.count()} reflection memories")


        self.memories: Dict[str, Memory] = {}
        self.user_profiles: Dict[str, Dict] = {}
        self.semantic_index: Dict[str, List[str]] = {}

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
    def store_memory(self, content: str, memory_type: str = "semantic",
                    user_id: str = None, importance: float = 1.0,
                    tags: List[str] = None, metadata: Dict = None) -> str:
        """Store a semantic memory in the system (episodic memories now use conversation_collection)."""
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
        """Retrieve semantic/procedural memories from JSON storage (conversations use conversation_collection)."""
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
                            logger.info(f"[Conversation Decay] Removed old conversation: '{content[:100]}{'...' if len(content) > 100 else ''}' (ID: {conv_id})")
                    except Exception as e:
                        logger.debug(f"Could not log decayed conversation {conv_id}: {e}")

                self.conversation_collection.delete(conversation_ids_to_delete)
                logger.info(f"[Conversation Decay] Successfully decayed {len(conversation_ids_to_delete)} conversation entries (1 minute lifetime)")

        except Exception as e:
            logger.debug(f"Error cleaning conversation collection: {e}")

    # === REFLECTION SYSTEM (Generative Agents Technique) ===
    async def _perform_reflection(self) -> None:
        """Perform reflection on recent messages to generate Q&A memories."""
        logger.info("[Reflection] Starting reflection process...")

        if not self.response_generator:
            logger.warning("No response generator available for reflection")
            return

        recent_messages = self.get_recent_chat_history(limit=self.reflection_threshold)
        logger.info(f"[Reflection] Retrieved {len(recent_messages)} recent messages for analysis")

        if len(recent_messages) < 10:
            logger.info(f"[Reflection] Skipping reflection - only {len(recent_messages)} messages (need at least 10)")
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
            logger.info(f"[Reflection] Successfully parsed {len(qa_pairs)} Q&A pairs from reflection response")

            for i, (question, answer) in enumerate(qa_pairs, 1):
                qa_memory = f"Q: {question}\nA: {answer}"
                reflection_id = str(uuid.uuid4())

                self.collection.upsert(
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
                logger.info(f"Stored reflection memory Q{i}: {question[:50]}...")

            self.message_counter = 0
            logger.info(f"[Reflection] Reflection process completed successfully - stored {len(qa_pairs)} new memories")

        except Exception as e:
            logger.error(f"[Reflection] Error during reflection process: {e}")

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

        message_id = str(uuid.uuid4())

        chromadb_metadata = {
            "role": role,
            "content": content,
            "user_id": user_id or "unknown",
            "timestamp": message["timestamp"],
            "type": "chat"
        }

        if metadata:
            for key, value in metadata.items():
                chromadb_metadata[f"meta_{key}"] = value

        self.conversation_collection.upsert(
            ids=[message_id],
            documents=[f"{role}: {content}"],
            metadatas=[chromadb_metadata]
        )

        self.message_counter += 1
        if self.message_counter >= self.reflection_threshold:
            logger.info(f"[Reflection] Triggering reflection after {self.message_counter} messages (threshold: {self.reflection_threshold})")
            asyncio.create_task(self._perform_reflection())

    def get_recent_chat_history(self, limit: int = 20) -> List[Dict]:
        """Get recent chat history from ChromaDB conversation collection."""
        try:
            results = self.conversation_collection.get(limit=limit)
            chat_history = []

            for i, item_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] and i < len(results['metadatas']) else {}

                chat_entry = {
                    "timestamp": metadata.get("timestamp", ""),
                    "role": metadata.get("role", "unknown"),
                    "content": results['documents'][i],
                    "user_id": metadata.get("user_id", "unknown"),
                    "metadata": {}
                }

                for key, value in metadata.items():
                    if key.startswith("meta_"):
                        chat_entry["metadata"][key[5:]] = value

                chat_history.append(chat_entry)

            return chat_history
        except Exception as e:
            logger.debug(f"Error retrieving chat history from ChromaDB: {e}")
            return []

    def get_user_chat_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Get chat history for a specific user from ChromaDB."""
        try:
            results = self.conversation_collection.get(
                where={"user_id": user_id},
                limit=limit
            )

            user_chat_history = []
            for i, item_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] and i < len(results['metadatas']) else {}

                chat_entry = {
                    "timestamp": metadata.get("timestamp", ""),
                    "role": metadata.get("role", "unknown"),
                    "content": results['documents'][i],
                    "user_id": metadata.get("user_id", "unknown"),
                    "metadata": {}
                }

                for key, value in metadata.items():
                    if key.startswith("meta_"):
                        chat_entry["metadata"][key[5:]] = value

                user_chat_history.append(chat_entry)

            return user_chat_history
        except Exception as e:
            logger.debug(f"Error retrieving user chat history from ChromaDB: {e}")
            return []

    # === COMPATIBILITY INTERFACE ===
    def add_chat_message(self, role: str, content: str, user_id: str = None,
                        metadata: Dict = None) -> None:
        """Add a chat message to conversation collection with 1-minute decay."""
        self.add_chat_message_sync(role, content, user_id, metadata)

        self.message_counter += 1
        if self.message_counter >= self.reflection_threshold:
            logger.info(f"[Reflection] Triggering reflection after {self.message_counter} messages (threshold: {self.reflection_threshold})")
            asyncio.create_task(self._perform_reflection())

    def get_memory_context(self, user_id: str = None, current_topic: str = None) -> str:
        """Generate memory context for prompts (enhanced version)."""
        context_parts = []

        if current_topic:
            try:
                reflection_results = self.collection.query(
                    query_texts=[current_topic],
                    n_results=2
                )
                if reflection_results["documents"]:
                    reflections = reflection_results["documents"][0]
                    context_parts.append(f"Key insights: {'; '.join(reflections)}")
            except Exception as e:
                logger.debug(f"Error querying ChromaDB reflections: {e}")

        if user_id:
            user_memories = self.retrieve_memories(
                user_id=user_id,
                memory_type="semantic",
                limit=2
            )
            if user_memories:
                memory_texts = [m.content for m in user_memories]
                context_parts.append(f"About user {user_id}: {'; '.join(memory_texts)}")

        if current_topic:
            topic_memories = self.retrieve_memories(
                query=current_topic,
                limit=1,
                min_relevance=0.1
            )
            if topic_memories:
                memory_texts = [m.content for m in topic_memories]
                context_parts.append(f"Related memories: {'; '.join(memory_texts)}")

        recent_memories = self.retrieve_memories(
            memory_type="semantic",
            limit=1
        )
        if recent_memories:
            memory_texts = [m.content for m in recent_memories]
            context_parts.append(f"Recent context: {'; '.join(memory_texts)}")

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

        conversation_count = 0
        reflection_count = 0

        try:
            conversation_count = self.conversation_collection.count()
            reflection_count = self.collection.count()
        except Exception as e:
            logger.debug(f"Error getting ChromaDB counts: {e}")

        return {
            "total_memories": len(self.memories),
            "chromadb_memories": {
                "conversations": conversation_count,
                "reflections": reflection_count
            },
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