import chromadb
from chromadb.config import Settings
from datetime import datetime
import uuid
from typing import Dict, List

class ChatHistoryManager:
    def __init__(self, chroma_client: chromadb.Client, conversation_collection_name: str, reflections_collection_name: str):
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
        """Add a chat message to persistent history (synchronous version)."""
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
            print(f"Error retrieving chat history from ChromaDB: {e}")
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
            print(f"Error retrieving user chat history from ChromaDB: {e}")
            return []

    def get_recent_reflections(self, limit: int = 20) -> List[Dict]:
        """Get recent reflections from ChromaDB collection."""
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
        """Get recent chat history and reflections combined."""
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