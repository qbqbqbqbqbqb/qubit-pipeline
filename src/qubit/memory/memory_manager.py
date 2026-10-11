"""
MemoryManager — low-level owner of ChromaDB collections + SQLite index.

LAYER: Memory (see ARCHITECTURE.md)

This class is the single place that talks directly to the persistent stores.
It is deliberately narrow:

- CRUD for conversation items and reflections
- Timestamp normalization + locking for thread safety
- Delegation to ReflectionGenerator when asked
- Internal SQL index for fast recency queries

It must remain free of:
- Decision logic or background loops (those live in MemoryService)
- Write routing (that lives in MemoryWriter)
- Prompt assembly (MemoryService contributes injections via the bus)

SQLite calls are all wrapped in run_in_executor so they do not block the
asyncio event loop. The lock (threading.Lock) is held inside the executor
thread, not on the async side.
"""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from functools import partial
import uuid
from typing import Any, Dict, List, Optional, Tuple

import chromadb

from src.qubit.memory.reflections_generator import ReflectionGenerator
from src.qubit.utils.log_utils import get_logger
from src.qubit.models.llm_service import LLMService


class MemoryManager:
    """
    Low-level manager for the two Chroma collections + SQLite recency index.

    Responsibilities (strict per Memory layer):
    - Own the raw collections ("chat", "reflections")
    - Provide thread-safe add/get/update operations
    - Normalize all timestamps to unix floats
    - Delegate reflection generation to ReflectionGenerator
    - Maintain a fast SQLite index for "recent items" queries

    It is the only component allowed to call chromadb.Client directly.
    Higher layers (MemoryService, MemoryWriter) talk to this class only.
    """

    def __init__(
        self,
        chroma_client: chromadb.Client,
        reflections_generator: Optional[ReflectionGenerator] = None,
        conn=None,
        llm_service: Optional[LLMService] = None,
    ):
        self.logger = get_logger("MemoryManager")
        self.chroma_client = chroma_client
        self.llm_service = llm_service

        self.collections = {
            "chat": self.chroma_client.get_or_create_collection(
                name="conversation_collection", metadata={"hnsw:space": "l2"}
            ),
            "reflections": self.chroma_client.get_or_create_collection(
                name="reflections_collection", metadata={"hnsw:space": "l2"}
            ),
        }
        self.reflections_generator = reflections_generator
        self.conn = conn
        self.lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_unix_ts(self, ts: Any) -> float:
        """
        Normalize any timestamp representation to a UTC unix float.

        Accepts: None, int/float seconds, datetime (naive or aware), ISO string.
        Falls back to now() on any parse failure.
        """
        if ts is None:
            return datetime.now(timezone.utc).timestamp()
        if isinstance(ts, (int, float)):
            return float(ts)
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.timestamp()
        if isinstance(ts, str):
            try:
                s = ts.rstrip("Z") + ("+00:00" if ts.endswith("Z") else "")
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except Exception:
                pass
        return datetime.now(timezone.utc).timestamp()

    async def _run_db(self, fn, *args, **kwargs):
        """Run a blocking SQLite call in the default thread pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    def _sqlite_insert(self, item_id: str, timestamp: float, user_id: str, type_: str, collection: str) -> None:
        """Blocking SQLite insert — must be called via _run_db."""
        with self.lock:
            self.conn.execute(
                "INSERT INTO memory_index (id, timestamp, user_id, type, collection) VALUES (?, ?, ?, ?, ?)",
                (item_id, timestamp, user_id, type_, collection),
            )
            self.conn.commit()

    def _sqlite_query_ids(self, collection_name: str, cutoff: float, limit: int) -> list:
        """Blocking SQLite SELECT — must be called via _run_db."""
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
                (collection_name, cutoff, limit),
            )
            return [row[0] for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def add_conversation_item(
        self,
        role: str,
        content: str,
        user_id: str = None,
        metadata: dict = None,
    ) -> None:
        """
        Persist a single conversation turn to Chroma + SQLite.

        The "reflected" flag starts False; MemoryService flips it after
        reflections are generated.
        """
        self.logger.info("[add_conversation_item] role=%s user=%s", role, user_id)

        coll = self.collections["chat"]
        try:
            item_id = str(uuid.uuid4())
            raw_ts = (metadata or {}).get("timestamp")
            timestamp = self._to_unix_ts(raw_ts)
            source = (metadata or {}).get("source", "Unknown")

            chroma_meta = {
                "user_id": user_id or "Unknown",
                "role": role,
                "timestamp": timestamp,
                "type": source,
                "reflected": False,
            }

            with self.lock:
                coll.upsert(ids=[item_id], documents=[content], metadatas=[chroma_meta])

            await self._run_db(
                self._sqlite_insert,
                item_id, timestamp, user_id or "Unknown", "chat", "conversation_collection",
            )

        except Exception as e:
            self.logger.error("[add_conversation_item] Error: %s", e)

    async def add_reflection_item(self, content: str) -> None:
        """Persist a generated reflection Q&A pair into the reflections collection."""
        self.logger.info("[add_reflection_item] adding reflection")
        coll = self.collections["reflections"]
        try:
            item_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).timestamp()

            with self.lock:
                coll.upsert(
                    ids=[item_id],
                    documents=[content],
                    metadatas=[{"timestamp": timestamp, "type": "reflection"}],
                )

            await self._run_db(
                self._sqlite_insert,
                item_id, timestamp, "system", "reflection", "reflections_collection",
            )

        except Exception as e:
            self.logger.error("[add_reflection_item] Error: %s", e)

    async def get_recent_items(
        self,
        collection_type: str,
        limit: int = 20,
        max_age_minutes: int = 120,
    ) -> List[Dict]:
        """
        Return the most recent items from either "chat" or "reflections".

        Uses SQLite for fast ID selection, then fetches documents from Chroma.
        """
        if collection_type not in self.collections:
            raise ValueError("Invalid collection: %s" % collection_type)

        coll = self.collections[collection_type]
        coll_name = (
            "conversation_collection" if collection_type == "chat" else "reflections_collection"
        )

        try:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            ).timestamp()

            ids = await self._run_db(self._sqlite_query_ids, coll_name, cutoff, limit)

            if not ids:
                return []

            with self.lock:
                results = coll.get(ids=ids)

            items = []
            for i in range(len(results["ids"])):
                meta = results["metadatas"][i]
                ts = self._to_unix_ts(meta.get("timestamp", 0.0))
                items.append({
                    "id": results["ids"][i],
                    "timestamp": ts,
                    "role": meta.get("role", "Unknown"),
                    "content": results["documents"][i],
                    "user_id": meta.get("user_id", "Unknown"),
                    "reflected": meta.get("reflected", False),
                })

            items = [it for it in items if it["timestamp"] >= cutoff]
            items.sort(key=lambda x: x["timestamp"], reverse=True)
            return items[:limit]

        except Exception as e:
            self.logger.error("[get_recent_items] Error retrieving %s: %s", collection_type, e)
            return []

    async def update_items_metadata(self, item_ids: List[str], new_metadata: Dict) -> None:
        """
        Patch metadata on a batch of chat items in Chroma.

        Called by MemoryService after reflection generation to mark items as
        reflected so they are not processed again.
        """
        coll = self.collections["chat"]
        try:
            def _update():
                with self.lock:
                    for item_id in item_ids:
                        existing = coll.get(ids=[item_id])
                        if existing["metadatas"]:
                            updated = {**existing["metadatas"][0], **new_metadata}
                            coll.update(ids=[item_id], metadatas=[updated])
            await self._run_db(_update)
        except Exception as e:
            self.logger.error("[update_items_metadata] Error: %s", e)

    async def generate_reflections(self) -> List[Tuple[str, str]]:
        """
        Trigger ReflectionGenerator to produce Q&A pairs from recent chat.

        Called from MemoryService's background worker.
        """
        self.logger.info("[generate_reflections] Generating reflections")
        if self.reflections_generator is None:
            raise ValueError("Reflections generator not set")
        try:
            reflections = await self.reflections_generator.perform_reflection(self)
            self.logger.info("[generate_reflections] Generated %s pairs", len(reflections))
            return reflections
        except Exception as e:
            self.logger.error("[generate_reflections] Error: %s", e)
            return []
