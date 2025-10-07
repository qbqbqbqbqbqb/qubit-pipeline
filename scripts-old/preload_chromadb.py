import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import chromadb
from chromadb.config import Settings

def preload_chromadb_models():
    """Pre-download ChromaDB sentence transformer models."""
    print("Pre-loading ChromaDB models...")

    try:
        chroma_client = chromadb.PersistentClient(
            path="./memories/chroma.db",
            settings=Settings(
                anonymized_telemetry=False,
                chroma_server_host=None,
                chroma_server_http_port=None
            )
        )

        collection = chroma_client.get_or_create_collection(
            name="reflections_collection",
            metadata={"hnsw:space": "cosine"}
        )

        print(f"Current collection count: {collection.count()}")

        print("⬇Downloading sentence transformer model...")

        collection.upsert(
            ids=["preload_dummy"],
            documents=["This is a dummy document to preload the sentence transformer model for ChromaDB."],
            metadatas=[{"type": "preload"}]
        )

        results = collection.query(query_texts=["test query"], n_results=1)
        print("Model query successful")

        collection.delete(["preload_dummy"])
        print("Cleaned up dummy data")

        print("ChromaDB models pre-loaded successfully!")

    except Exception as e:
        print(f"Error pre-loading ChromaDB models: {e}")
        return False

    return True

if __name__ == "__main__":
    success = preload_chromadb_models()
    if success:
        print("\nReady to start.")
    else:
        print("\nPre-loading failed. Check your internet connection and try again.")
        sys.exit(1)