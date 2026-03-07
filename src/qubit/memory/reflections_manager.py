from datetime import datetime
from typing import Dict
import uuid
import chromadb
from qubit.memory.reflections_generator import ReflectionGenerator
from src.utils.log_utils import get_logger


class ReflectionsManager:
    def __init__(self, chroma_client: chromadb.Client, reflections_collection_name: str = "reflections", reflection_generator: ReflectionGenerator =None):
        """
        Initialize the ReflectionsManager with ChromaDB client and collection names.
        """
        self.logger = get_logger("ReflectionsManager")
        self.chroma_client = chroma_client
        self.reflections_collection = self.chroma_client.get_or_create_collection(
            name=reflections_collection_name,
            metadata={"hnsw:space": "l2"}
        )
        self.reflection_generator = reflection_generator


    def create_reflection(self) -> None:
        if self.reflection_generator:
            reflections = self.reflection_generator.perform_reflection()
            for q, a in reflections:
                self.add_reflection_item(content=f"Q: {q}\nA: {a}")

    def add_reflection_item(self, content: str) -> None:
        """
        Add a chat message to the persistent conversation history synchronously.
        """
        self.logger.info(f"adding reflection item: {content}")

        try:
            chromadb_metadata = {
                "timestamp": datetime.now().isoformat(),
                "type": "reflection",
                "content": content,
            }

            self.reflections_collection.upsert(
                ids=str(uuid.uuid4()),
                documents=[f"{content}"],
                metadatas=[chromadb_metadata]
            )
        except Exception as e:
            self.logger.error(f"Error adding reflection item: {e}")

    def get_most_recent_reflection(self):
        try:
            results = self.reflections_collection.get(limit=1)

            metadata = results['metadatas'][0] if results['metadatas'] else {}

            return [{
                "timestamp": metadata.get("timestamp", ""),
                "content": results['documents'][0],
                "user_id": metadata.get("user_id", "unknown"),
            }]

        except Exception as e:
            print(f"Error retrieving reflections from ChromaDB: {e}")
            return []