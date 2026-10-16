"""
<summary>
MemoryManager — low-level owner of ChromaDB collections and the SQLite recency index.
</summary>
<remarks>
LAYER: Memory

Single place that talks directly to persistent stores. Deliberately narrow:
  - CRUD for conversation items and reflections
  - Timestamp normalisation and threading lock for thread safety
  - Delegation to ReflectionGenerator when asked
  - Internal SQL index for fast recency queries

Must remain free of:
  - Decision logic or background loops (those live in MemoryService)
  - Write routing (that lives in MemoryWriter)
  - Prompt assembly (MemoryService contributes injections via the bus)

SQLite calls are all wrapped in run_in_executor so they do not block the
asyncio event loop. The lock (threading.Lock) is held inside the executor
thread, not on the async side.
</remarks>
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
    <summary>
    Low-level manager for the chat and reflections Chroma collections plus the SQLite recency index.
    The only component permitted to call chromadb directly. Higher layers call this class only.
    </summary>
    """

    def __init__(
        self,
        chroma_client: chromadb.Client,
        reflections_generator: Optional[ReflectionGenerator] = None,
        conn=None,
        llm_service: Optional[LLMService] = None,
    ):
        """
        <summary>Initialise Chroma collections and the SQLite connection.</summary>
        <param name="chroma_client">The persistent ChromaDB client.</param>
        <param name="reflections_generator">Optional generator for reflection Q&A pairs.</param>
        <param name="conn">The shared SQLite connection for the recency index.</param>
        <param name="llm_service">LLM service, passed through to the reflections generator if needed.</param>
        """
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

    def _to_unix_ts(self, ts: Any) -> float:
        """
        <summary>
        Normalise any timestamp representation to a UTC unix float.
        Accepts None, int/float seconds, datetime (naive or aware), and ISO strings.
        Falls back to now() on any parse failure.
        </summary>
        <param name="ts">The timestamp value to normalise.</param>
        <returns>UTC unix timestamp as a float.</returns>
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
        """
        <summary>Run a blocking SQLite call in the default thread pool executor.</summary>
        <param name="fn">The blocking function to call.</param>
        <returns>The function's return value.</returns>
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    def _sqlite_insert(self, item_id: str, timestamp: float, user_id: str, type_: str, collection: str) -> None:
        """
        <summary>Blocking SQLite insert for the memory index. Must be called via _run_db.</summary>
        <param name="item_id">UUID for the new row.</param>
        <param name="timestamp">UTC unix float timestamp.</param>
        <param name="user_id">User identifier string.</param>
        <param name="type_">Item type label (e.g. 'chat', 'reflection').</param>
        <param name="collection">Chroma collection name.</param>
        """
        with self.lock:
            self.conn.execute(
                "INSERT INTO memory_index (id, timestamp, user_id, type, collection) VALUES (?, ?, ?, ?, ?)",
                (item_id, timestamp, user_id, type_, collection),
            )
            self.conn.commit()

    def _sqlite_query_ids(self, collection_name: str, cutoff: float, limit: int) -> list:
        """
        <summary>Blocking SQLite SELECT for recent item ids. Must be called via _run_db.</summary>
        <param name="collection_name">Chroma collection name to query.</param>
        <param name="cutoff">Minimum unix timestamp (items older than this are excluded).</param>
        <param name="limit">Maximum number of ids to return.</param>
        <returns>List of id strings ordered newest-first.</returns>
        """
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

    async def add_conversation_item(
        self,
        role: str,
        content: str,
        user_id: str = None,
        metadata: dict = None,
    ) -> None:
        """
        <summary>Persist a single conversation turn to Chroma and the SQLite index.</summary>
        <remarks>
        The 'reflected' flag is stored as False on creation. MemoryService flips it after
        reflections are generated from the item.
        </remarks>
        <param name="role">Speaker role string (e.g. 'User', 'Qubit', 'System').</param>
        <param name="content">The text content to store.</param>
        <param name="user_id">Optional user identifier for the index.</param>
        <param name="metadata">Optional metadata dict; 'timestamp' and 'source' are read if present.</param>
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

            def _chroma_upsert():
                with self.lock:
                    coll.upsert(ids=[item_id], documents=[content], metadatas=[chroma_meta])

            await self._run_db(_chroma_upsert)
            await self._run_db(
                self._sqlite_insert,
                item_id, timestamp, user_id or "Unknown", "chat", "conversation_collection",
            )

        except Exception as e:
            self.logger.error("[add_conversation_item] Error: %s", e)

    async def add_reflection_item(self, content: str) -> None:
        """
        <summary>Persist a generated reflection Q&A pair into the reflections collection.</summary>
        <param name="content">The formatted 'Q: ...\nA: ...' string to store.</param>
        """
        self.logger.info("[add_reflection_item] Adding reflection")
        coll = self.collections["reflections"]
        try:
            item_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).timestamp()

            def _chroma_upsert():
                with self.lock:
                    coll.upsert(
                        ids=[item_id],
                        documents=[content],
                        metadatas=[{"timestamp": timestamp, "type": "reflection"}],
                    )

            await self._run_db(_chroma_upsert)
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
        <summary>
        Return the most recent items from either 'chat' or 'reflections'.
        Uses SQLite for fast id selection, then fetches documents from Chroma.
        </summary>
        <param name="collection_type">Either 'chat' or 'reflections'.</param>
        <param name="limit">Maximum number of items to return.</param>
        <param name="max_age_minutes">Items older than this many minutes are excluded.</param>
        <returns>List of item dicts sorted newest-first, each with id, timestamp, role, content, user_id, reflected.</returns>
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

            def _chroma_get():
                with self.lock:
                    return coll.get(ids=ids)

            results = await self._run_db(_chroma_get)

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
        <summary>
        Patch metadata on a batch of chat items in Chroma.
        Called by MemoryService after reflection generation to mark items as reflected.
        </summary>
        <param name="item_ids">List of Chroma document ids to update.</param>
        <param name="new_metadata">Metadata fields to merge into each item's existing metadata.</param>
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
        <summary>Trigger ReflectionGenerator to produce Q&A pairs from recent chat.</summary>
        <returns>A list of (question, answer) string tuples, or an empty list on failure.</returns>
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
