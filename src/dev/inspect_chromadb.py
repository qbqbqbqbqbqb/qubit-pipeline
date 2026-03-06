"""
ChromaDB Inspector Module

This module provides functionality to inspect and display contents of ChromaDB collections
used in the bot's memory system. It connects to the persistent ChromaDB instance and prints
detailed information about each collection, including item counts, content previews, and metadata.

Useful for debugging memory storage, verifying data persistence, and understanding the
structure of stored memories, chat history, monologues, and reflections.

Functions:
    inspect_chromadb(): Main function to perform the inspection.
"""

import sys
import os
from pathlib import Path
from config.config import ROOT
import chromadb
from chromadb.config import Settings

def inspect_chromadb():
    """
    Inspect and display contents of all ChromaDB collections.

    This function connects to the bot's ChromaDB instance located at ROOT/memories/chroma.db
    and retrieves information about all collections. For each collection, it prints the total
    number of items and detailed information about each item, including ID, content preview,
    and associated metadata.

    Useful for debugging memory storage and verifying data persistence.

    Args:
        None

    Returns:
        None

    Raises:
        Exception: If there is an error connecting to ChromaDB or retrieving collections.
    """
    try:
        chroma_client = chromadb.PersistentClient(
            path=str(ROOT / "memories" / "chroma.db"),
            settings=Settings(
                anonymized_telemetry=False,
                chroma_server_host=None,
                chroma_server_http_port=None
            )
        )

        print("ChromaDB Collections Inspector")
        print("=" * 50)

        collections = chroma_client.list_collections()
        collection_names = [col.name for col in collections]

        print(f"Found {len(collection_names)} collections: {collection_names}")
        print()

        for collection_name in collection_names:
            print(f"Collection: {collection_name}")
            print("-" * 30)

            collection = chroma_client.get_collection(collection_name)

            results = collection.get(limit=1000)

            count = len(results['ids']) if results['ids'] else 0
            print(f"Total items: {count}")

            if count == 0:
                print("  (empty)")
                print()
                continue

            for i, item_id in enumerate(results['ids']):
                document = results['documents'][i] if i < len(results['documents']) else "N/A"
                metadata = results['metadatas'][i] if results['metadatas'] and i < len(results['metadatas']) else {}

                print(f"\n  Item {i+1} (ID: {item_id})")
                print(f"     Content: {document[:100]}{'...' if len(document) > 100 else ''}")

                if metadata:
                    print("     Metadata:")
                    for key, value in metadata.items():
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        print(f"       {key}: {value}")
                else:
                    print("     Metadata: (none)")

            print()

        print("Inspection complete!")
    except Exception as e:
        print(f"Error inspecting ChromaDB: {e}")


if __name__ == "__main__":
    inspect_chromadb()