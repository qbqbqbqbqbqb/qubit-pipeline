import chromadb
from chromadb.config import Settings
from datetime import datetime
import uuid
from typing import Dict, List

from src.utils.log_utils import get_logger

"""
Chat History Manager Module

This module provides functionality for managing chat history and reflections using ChromaDB.
It includes the ChatHistoryManager class which handles storing and retrieving chat messages
and AI-generated reflections in a vector database for efficient querying and context provision.

The module supports synchronous operations for adding conversation items and retrieving
recent chat history, user-specific history, and reflections. It integrates with ChromaDB
for persistent storage and vector-based search capabilities.

Classes:
    ChatHistoryManager: Main class for managing chat history and reflections.

Dependencies:
    - chromadb: For vector database operations
    - datetime: For timestamp handling
    - uuid: For generating unique message IDs
    - typing: For type hints
"""

class ChatHistoryManager:
    """
    Chat History Manager class for handling chat conversations and AI reflections.
    This class provides methods to add chat messages to a persistent conversation history
    """
    def __init__(self, chroma_client: chromadb.Client, conversation_collection_name: str = "chat"):
        """
        Initialize the ChatHistoryManager with ChromaDB client and collection names.
        """
        self.logger = get_logger("ChatHistoryManager")
        self.chroma_client = chroma_client
        self.conversation_collection = self.chroma_client.get_or_create_collection(
            name=conversation_collection_name,
            metadata={"hnsw:space": "l2"}
        )

    def add_conversation_item_sync(self, role: str, content: str, user_id: str = None,
                             metadata: Dict = None) -> None:
        """
        Add a chat message to the persistent conversation history synchronously.
        """
        self.logger.info(f"adding message: {content} with {metadata} from {role} {user_id}")
        try:
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
        except Exception as e:
            print(f"Error adding chat message: {e}")

    