"""
Script to inspect ChromaDB collections and their contents.
Shows all stored memories, chat history, monologues, and reflections.
"""

import sys
import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

def inspect_chromadb():
    """Inspect all ChromaDB collections and their contents."""

    base_path = Path(__file__).parent.parent
    chroma_client = chromadb.PersistentClient(
        path=str(base_path / "memories" / "chroma.db"),
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


if __name__ == "__main__":
    inspect_chromadb()