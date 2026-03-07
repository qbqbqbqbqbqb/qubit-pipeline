import chromadb
from datetime import datetime, timedelta, timezone
import uuid
from typing import Dict, List, Tuple
import re
import asyncio

from src.qubit.memory.reflections_generator import ReflectionGenerator
from src.utils.log_utils import get_logger
from src.qubit.processing.prompt_dispatcher import PromptDispatcher
from config.config import MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION

class MemoryManager:
    def __init__(self, chroma_client: chromadb.Client,  dispatcher: PromptDispatcher = None, reflections_generator: ReflectionGenerator = None):
        self.logger = get_logger("MemoryManager")
        self.chroma_client = chroma_client
        self.dispatcher = dispatcher
        self.collections = {
            "chat": self.chroma_client.get_or_create_collection(name="conversation_collection", metadata={"hnsw:space": "l2"}),
            "reflections": self.chroma_client.get_or_create_collection(name="reflections_collection", metadata={"hnsw:space": "l2"})
        }
        self.reflections_generator = reflections_generator

    def add_conversation_item(self, role: str, content: str, user_id: str = None, metadata: dict = None) -> None:
        """
        Add a chat message to the persistent conversation history.
        """
        self.logger.info(f"adding message: {content} from {role} {user_id}")
        coll = self.collections["chat"]
        try:
            chromadb_metadata = {
                "user_id": user_id or "Unknown",
                "role": role,
                "timestamp": metadata.get("timestamp", datetime.now().isoformat()) if metadata else datetime.now().isoformat(),
                "type": metadata.get("source", "Unknown") if metadata else "Unknown",
            }

            coll.upsert(
                ids=[str(uuid.uuid4())],
                documents=[f"{role}: {content}"],
                metadatas=[chromadb_metadata]
            )
        except Exception as e:
            self.logger.error(f"Error adding chat message: {e}")

    def add_reflection_item(self, content: str) -> None:
        """
        Add a reflection to the persistent reflections collection.
        """
        self.logger.info(f"adding reflection item: {content}")
        coll = self.collections["reflections"]
        try:
            chromadb_metadata = {
                "timestamp": datetime.now().isoformat(),
                "type": "reflection",
                "content": content,
            }

            coll.upsert(
                ids=[str(uuid.uuid4())],
                documents=[f"{content}"],
                metadatas=[chromadb_metadata]
            )
        except Exception as e:
            self.logger.error(f"Error adding reflection item: {e}")

    def get_recent_items(self, collection_type: str, limit: int = 20, max_age_minutes: int = 120) -> List[Dict]:
        if collection_type not in self.collections:
            raise ValueError(f"Invalid collection: {collection_type}")
        coll = self.collections[collection_type]
        try:
            results = coll.get(limit=limit)
            items = []

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=max_age_minutes)
        
            for i in range(len(results['ids'])):
                meta = results['metadatas'][i] if i < len(results['metadatas']) else {}

                timestamp_str = meta.get("timestamp")
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str)

                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                #print(f"timestamp: {timestamp}, cutoff: {cutoff}")
                if timestamp < cutoff:
                    continue

                items.append({
                    "timestamp": meta.get("timestamp", ""),
                    "role": meta.get("role", "Unknown"),
                    "content": results['documents'][i] if i < len(results['documents']) else "",
                    "user_id": meta.get("user_id", "Unknown")
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

    def generate_reflections(self):
        self.reflections_generator.perform_reflection()