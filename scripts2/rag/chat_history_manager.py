import chromadb
from chromadb.config import Settings
from datetime import datetime
import uuid
from typing import Dict, List

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

    This class provides methods to store and retrieve chat messages and reflections
    in ChromaDB collections. It manages two separate collections: one for conversation
    history with L2 space and another for reflections with cosine space.

    Attributes:
        chroma_client (chromadb.Client): The ChromaDB client instance.
        conversation_collection: ChromaDB collection for chat messages.
        collection: ChromaDB collection for reflections.
    """
    def __init__(self, chroma_client: chromadb.Client, conversation_collection_name: str, reflections_collection_name: str):
        """
        Initialize the ChatHistoryManager with ChromaDB client and collection names.

        Args:
            chroma_client (chromadb.Client): The ChromaDB client instance to use for database operations.
            conversation_collection_name (str): Name of the collection to store chat conversation history.
            reflections_collection_name (str): Name of the collection to store AI-generated reflections.

        The method creates or retrieves two collections:
        - conversation_collection: For chat messages, using L2 distance metric.
        - collection: For reflections, using cosine distance metric.
        """
        self.chroma_client = chroma_client
        self.conversation_collection = self.chroma_client.get_or_create_collection(
            name=conversation_collection_name,
            metadata={"hnsw:space": "l2"}
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name=reflections_collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def add_conversation_item_sync(self, role: str, content: str, user_id: str = None,
                             metadata: Dict = None) -> None:
        """
        Add a chat message to the persistent conversation history synchronously.

        This method stores a chat message in the ChromaDB conversation collection,
        including metadata for efficient querying and retrieval. The message is
        timestamped and assigned a unique ID.

        Args:
            role (str): The role of the message sender (e.g., 'user', 'qubit').
            content (str): The text content of the chat message.
            user_id (str, optional): Identifier for the user. Defaults to None.
            metadata (Dict, optional): Additional metadata to store with the message.
                Will be prefixed with 'meta_' in ChromaDB. Defaults to None.

        Returns:
            None

        Raises:
            Exception: If there's an error adding the message to ChromaDB.
        """
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

    def get_recent_chat_history(self, limit: int = 20) -> List[Dict]:
        """
        Retrieve recent chat history from the ChromaDB conversation collection.

        This method fetches the most recent chat messages stored in the conversation
        collection, up to the specified limit. Messages are returned in the order
        they were stored, with metadata properly parsed.

        Args:
            limit (int, optional): Maximum number of chat entries to retrieve. Defaults to 20.

        Returns:
            List[Dict]: A list of dictionaries, each containing chat entry information:
                - 'timestamp': ISO formatted timestamp string
                - 'role': Role of the message sender
                - 'content': The message content
                - 'user_id': User identifier
                - 'metadata': Additional metadata dictionary

        Raises:
            Exception: If there's an error retrieving data from ChromaDB.
        """
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

            chat_history.sort(key=lambda x: x["timestamp"], reverse=True)

            return chat_history[:limit]
    
        except Exception as e:
            print(f"Error retrieving chat history from ChromaDB: {e}")
            return []

    def get_user_chat_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        Retrieve chat history for a specific user from the ChromaDB conversation collection.

        This method queries the conversation collection for messages associated with
        the given user ID, returning up to the specified limit of most recent entries.

        Args:
            user_id (str): The identifier of the user whose chat history to retrieve.
            limit (int, optional): Maximum number of chat entries to retrieve. Defaults to 10.

        Returns:
            List[Dict]: A list of dictionaries, each containing user chat entry information:
                - 'timestamp': ISO formatted timestamp string
                - 'role': Role of the message sender
                - 'content': The message content
                - 'user_id': User identifier (should match the queried user_id)
                - 'metadata': Additional metadata dictionary

        Raises:
            Exception: If there's an error retrieving data from ChromaDB.
        """
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
            print(f"Error retrieving user chat history from ChromaDB: {e}")
            return []

    def get_recent_reflections(self, limit: int = 20) -> List[Dict]:
        """
        Retrieve recent reflections from the ChromaDB reflections collection.

        This method fetches AI-generated reflections stored in the reflections collection,
        sorted by creation time in descending order, and returns up to the specified limit.
        It retrieves more entries internally (up to 1000) to ensure proper sorting.

        Args:
            limit (int, optional): Maximum number of reflections to retrieve. Defaults to 20.

        Returns:
            List[Dict]: A list of dictionaries, each containing reflection information:
                - 'document': The reflection text content
                - 'metadata': Full metadata dictionary from ChromaDB
                - 'created_at': Timestamp string from metadata

        Raises:
            Exception: If there's an error retrieving data from ChromaDB.
        """
        try:
            results = self.collection.get(limit=1000)
            reflections = []
            for i, doc in enumerate(results['documents']):
                metadata = results['metadatas'][i]
                reflections.append({
                    "document": doc,
                    "metadata": metadata,
                    "created_at": metadata.get("created_at", "")
                })
            reflections.sort(key=lambda x: x['created_at'], reverse=True)
            return reflections[:limit]
        except Exception as e:
            print(f"Error retrieving recent reflections: {e}")
            return []

    def get_recent_memories(self, limit_chat: int = 20, limit_reflections: int = 20) -> Dict[str, List[Dict]]:
        """
        Retrieve recent chat history and reflections combined into a single response.

        This method aggregates recent chat messages and AI reflections, formatting
        reflections to match the chat history structure for unified processing.
        Reflections are presented with a 'reflection' role and 'system' user_id.

        Args:
            limit_chat (int, optional): Maximum number of chat entries to retrieve. Defaults to 20.
            limit_reflections (int, optional): Maximum number of reflections to retrieve. Defaults to 20.

        Returns:
            Dict[str, List[Dict]]: A dictionary with two keys:
                - 'chat_history': List of recent chat entries (same format as get_recent_chat_history)
                - 'reflections': List of formatted reflection entries with keys:
                    - 'timestamp': Creation timestamp
                    - 'role': Always 'reflection'
                    - 'content': Reflection text
                    - 'user_id': Always 'system'
                    - 'metadata': Full reflection metadata

        Raises:
            Exception: If there's an error retrieving data from ChromaDB.
        """
        chat_history = self.get_recent_chat_history(limit=limit_chat)

        recent_reflections = self.get_recent_reflections(limit=limit_reflections)

        formatted_reflections = []
        for ref in recent_reflections:
            formatted_reflections.append({
                "timestamp": ref["metadata"].get("created_at", ""),
                "role": "reflection",
                "content": ref["document"],
                "user_id": "system",
                "metadata": ref["metadata"]
            })

        return {
            "chat_history": chat_history,
            "reflections": formatted_reflections
        }