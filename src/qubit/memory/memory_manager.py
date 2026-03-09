import chromadb
from datetime import datetime, timedelta, timezone
import uuid
from typing import Dict, List, Tuple
import re
import asyncio
import threading  # Added for Lock

from src.qubit.memory.reflections_generator import ReflectionGenerator
from src.utils.log_utils import get_logger
from src.qubit.processing.prompt_dispatcher import PromptDispatcher
from config.config import MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION

class MemoryManager:
    def __init__(self, chroma_client: chromadb.Client, dispatcher: PromptDispatcher = None, reflections_generator: ReflectionGenerator = None, conn = None):
        self.logger = get_logger("MemoryManager")
        self.chroma_client = chroma_client
        self.dispatcher = dispatcher
        self.collections = {
            "chat": self.chroma_client.get_or_create_collection(name="conversation_collection", metadata={"hnsw:space": "l2"}),
            "reflections": self.chroma_client.get_or_create_collection(name="reflections_collection", metadata={"hnsw:space": "l2"})
        }
        self.reflections_generator = reflections_generator
        self.conn = conn
        self.lock = threading.Lock()  # Added to serialize SQLite access

    def add_conversation_item(self, role: str, content: str, user_id: str = None, metadata: dict = None) -> None:
        """
        Add a chat message to the persistent conversation history.
        """
        self.logger.info(f"adding message: {content} from {role} {user_id}")

        coll = self.collections["chat"]

        try:
            item_id = str(uuid.uuid4())

            timestamp = (
                metadata.get("timestamp")
                if metadata and "timestamp" in metadata
                else datetime.now(timezone.utc).isoformat()
            )

            source = (
                metadata.get("source")
                if metadata and "source" in metadata
                else "Unknown"
            )

            chromadb_metadata = {
                "user_id": user_id or "Unknown",
                "role": role,
                "timestamp": timestamp,
                "type": source,
            }

            coll.upsert(
                ids=[item_id],
                documents=[f"{role}: {content}"],
                metadatas=[chromadb_metadata]
            )

            with self.lock:
                self.conn.execute(
                    "INSERT INTO memory_index (id, timestamp, user_id, type, collection) VALUES (?, ?, ?, ?, ?)",
                    (item_id, timestamp, user_id or "Unknown", "chat", "conversation_collection")
                )
                self.conn.commit()

        except Exception as e:
            self.logger.error(f"Error adding chat message: {e}")

    def add_reflection_item(self, content: str) -> None:
        """
        Add a reflection to the persistent reflections collection.
        """
        self.logger.info(f"adding reflection item: {content}")
        coll = self.collections["reflections"]

        try:
            item_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            chromadb_metadata = {
                "timestamp": timestamp,
                "type": "reflection"
            }

            coll.upsert(
                ids=[item_id],
                documents=[content],
                metadatas=[chromadb_metadata]
            )

            with self.lock:
                self.conn.execute(
                    "INSERT INTO memory_index (id, timestamp, user_id, type, collection) VALUES (?, ?, ?, ?, ?)",
                    (item_id, timestamp, "system", "reflection", "reflections_collection")
                )
                self.conn.commit()

        except Exception as e:
            self.logger.error(f"Error adding reflection item: {e}")

    def get_recent_items(
        self,
        collection_type: str,
        limit: int = 20,
        max_age_minutes: int = 120
    ) -> List[Dict]:

        if collection_type not in self.collections:
            raise ValueError(f"Invalid collection: {collection_type}")

        coll = self.collections[collection_type]
        coll_name = "conversation_collection" if collection_type == "chat" else "reflections_collection"

        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()

            with self.lock:
                cursor = self.conn.execute(
                    """
                    SELECT id
                    FROM memory_index
                    WHERE collection = ?
                    AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (coll_name, cutoff, limit)
                )
                ids = [row[0] for row in cursor.fetchall()]

            if not ids:
                return []

            results = coll.get(ids=ids)

            items = []

            for i in range(len(results["ids"])):
                meta = results["metadatas"][i]
                items.append({
                    "id": results["ids"][i],
                    "timestamp": meta.get("timestamp", ""),
                    "role": meta.get("role", "Unknown"),
                    "content": results["documents"][i],
                    "user_id": meta.get("user_id", "Unknown"),
                    "reflected": meta.get("reflected", False)
                })

            items.sort(key=lambda x: x["timestamp"], reverse=True)

            return items[:limit]

        except Exception as e:
            self.logger.error(f"Error retrieving from {collection_type}: {e}")
            return []
        
    def update_items_metadata(self, item_ids: List[str], new_metadata: Dict) -> None:
        coll = self.collections["chat"] 
        try:
            for item_id in item_ids:
                existing = coll.get(ids=[item_id])
                if existing['metadatas']:
                    updated_meta = {**existing['metadatas'][0], **new_metadata}
                    coll.update(ids=[item_id], metadatas=[updated_meta])
        except Exception as e:
            self.logger.error(f"Error updating metadata for items: {e}")

    async def generate_reflections(self) -> List[Tuple[str, str]]:
        if self.reflections_generator is None:
            raise ValueError("Reflections generator not set")
        return await self.reflections_generator.perform_reflection(self)