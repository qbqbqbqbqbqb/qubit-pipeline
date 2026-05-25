"""
MemoryService — owner of persistent memory storage and background jobs.

This class is intentionally limited (see ARCHITECTURE.md Memory Layer):
- Storage ownership (Chroma + SQLite)
- Public history accessors for RAG
- Background reflection generation loop
- Narrow contribution to prompt assembly via the event bus

Write routing now lives in MemoryWriter (pure EventProcessor).
"""

import asyncio
from pathlib import Path
from typing import Dict, List
import sqlite3
from sqlite3 import Connection

import chromadb
from chromadb.config import Settings

from src.qubit.memory.reflections_generator import ReflectionGenerator
from src.qubit.models.llm_service import LLMService

from src.qubit.core.events import PromptAssemblyEvent
from src.qubit.prompting.modules.chat import chat_memory_module
from src.qubit.prompting.modules.reflection import reflection_memory_module
from src.qubit.core.service import Service
from src.qubit.memory.memory_manager import MemoryManager
from config.config import REFLECTIONS_THRESHOLD

class MemoryService(Service):
    """
    Memory subsystem owner.

    Responsibilities (per target architecture):
    - Owns the persistent stores (ChromaDB + SQLite index)
    - Owns MemoryManager (CRUD) and ReflectionsGenerator
    - Runs the background reflection generation job (_run)
    - Provides recent history for RAG via public getters
    - Contributes memory injections when the prompt assembly event is published

    It should NOT contain decision logic, prompt building, or write routing.
    Writes now go through MemoryWriter (EventProcessor).
    """

    SUBSCRIPTIONS = {"prompt_assembly": "handle_prompt_assembly"}

    def __init__(self, base_path: str = ".", llm_service: LLMService = None):
        super().__init__("MemoryService")

        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)
        self.sql_dir = self.memories_dir / "sql"
        self.sql_dir.mkdir(exist_ok=True)
        self.llm_service = llm_service

        self.chroma_client = chromadb.PersistentClient(
            path=str(self.memories_dir / "chroma.db"),
            settings=Settings(
                anonymized_telemetry=False,
                chroma_server_host=None,
                chroma_server_http_port=None
            )
        )
        db_path = self.sql_dir / "memory_index.db"
        self.conn: Connection = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row

        self.reflections_generator = ReflectionGenerator(
            llm_service=self.llm_service,
            reflection_profile="reflection",
        )
        self.memory_manager = MemoryManager(
            self.chroma_client,
            conn=self.conn,
            reflections_generator=self.reflections_generator,
            llm_service=self.llm_service,
        )
        with self.memory_manager.lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_index (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    user_id TEXT,
                    type TEXT,
                    collection TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_collection_timestamp ON memory_index (collection, timestamp)")
            self.conn.commit()

    async def start(self, app) -> None:
        await super().start(app)

    async def _run(self) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while True:
                await asyncio.sleep(60)
                self.logger.info("[_run] MemoryService worker checking for reflections...")
                recent_chats = self.memory_manager.get_recent_items("chat", limit=100, max_age_minutes=120)
                self.logger.info("[_run] Found %s recent chat items for reflection check", len(recent_chats))
                unreflected = [chat for chat in recent_chats if not chat.get("reflected", False)]
                self.logger.info("[_run] Found %s unreflected chat items", len(unreflected))
                if len(unreflected) >= REFLECTIONS_THRESHOLD:
                    self.logger.info("[_run] Creating reflections")
                    reflections = await self.memory_manager.generate_reflections()
                    self.logger.info("[_run] Generated %s reflections", len(reflections))
                    for q, a in reflections:
                        self.memory_manager.add_reflection_item(f"Q: {q}\nA: {a}")
                    ids_to_update = [chat["id"] for chat in unreflected]
                    self.logger.info("[_run] Marking %s chat items as reflected", len(ids_to_update))
                    self.memory_manager.update_items_metadata(ids_to_update, {"reflected": True})

    async def stop(self) -> None:
        await super().stop()

    def add_conversation_item(self, role: str, content: str, user_id: str = None, metadata: dict = None) -> None:
        """
        Add a conversation item to the chat history.
        """
        self.memory_manager.add_conversation_item(role, content, user_id, metadata=metadata)

    def get_recent_chat_history(self) -> List[Dict]:
        return self.memory_manager.get_recent_items("chat", limit=20)

    def get_recent_reflections(self) -> List[Dict]:
        return self.memory_manager.get_recent_items("reflections", limit=3)

    # ------------------------------------------------------------------
    # RAG injection support (narrow, explicit interface for prompt assembly)
    # ------------------------------------------------------------------

    def _get_chat_memory_injection(self):
        """Returns a PromptInjection for recent chat history, or None."""
        history = self.get_recent_chat_history()
        return chat_memory_module(history)

    def _get_reflection_memory_injection(self):
        """Returns a PromptInjection for recent reflections, or None."""
        reflections = self.get_recent_reflections()
        return reflection_memory_module(reflections)

    async def handle_prompt_assembly(self, event: PromptAssemblyEvent) -> None:
        """
        Contribute memory-based injections when the prompt is being assembled.

        This is the only place MemoryService participates in prompt construction.
        It appends (at most) two injections: recent chat + recent reflections.
        """
        if not hasattr(event, "contributions"):
            event.contributions = []

        chat_inj = self._get_chat_memory_injection()
        if chat_inj and chat_inj.content:
            event.contributions.append(chat_inj)

        refl_inj = self._get_reflection_memory_injection()
        if refl_inj and refl_inj.content:
            event.contributions.append(refl_inj)

        event.contributions.sort(key=lambda inj: inj.priority)
