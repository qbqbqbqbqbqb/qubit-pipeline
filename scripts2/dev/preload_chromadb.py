import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import chromadb
from chromadb.config import Settings
"""
Preload ChromaDB Models Script

This module provides functionality to pre-download and initialize ChromaDB sentence transformer models.
It ensures that the required models are available locally before the main application starts,
preventing delays during runtime due to model downloads.

The script can be run independently to preload models or imported as a module.
"""



def preload_chromadb_models():
    """
    Pre-download ChromaDB sentence transformer models.

    This function initializes a persistent ChromaDB client, creates or retrieves a collection,
    and performs operations to trigger the download of the sentence transformer model.
    It uses a dummy document insertion and query to ensure the model is loaded,
    then cleans up the dummy data.

    The process involves:
    - Creating a ChromaDB PersistentClient with specific settings.
    - Getting or creating a collection named 'reflections_collection' with cosine space.
    - Inserting a dummy document to force model download.
    - Querying the collection to verify model functionality.
    - Deleting the dummy document to clean up.

    Returns:
        bool: True if preloading was successful, False otherwise.

    Raises:
        Exception: Propagated if an error occurs during ChromaDB operations, though
                   internally caught and handled by returning False. Common issues
                   include network errors during model download or ChromaDB configuration problems.
    """
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