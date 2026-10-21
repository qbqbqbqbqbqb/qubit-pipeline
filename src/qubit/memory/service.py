"""
<summary>
MemoryService — owner of persistent memory storage and background reflection jobs.
</summary>
<remarks>
LAYER: Memory

Responsibilities:
  - Owns the persistent stores (ChromaDB + SQLite index)
  - Owns MemoryManager (CRUD) and ReflectionGenerator
  - Runs the background reflection generation job (_run)
  - Provides recent history for RAG via public getters
  - Contributes memory injections when the prompt_assembly event is published

Must remain free of:
  - Decision logic
  - Prompt construction (contributions are narrow injection objects only)
  - Write routing (that lives in MemoryWriter)
</remarks>
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
from config.settings import REFLECTIONS_THRESHOLD


class MemoryService(Service):
    """
    <summary>
    Service that owns ChromaDB, SQLite, MemoryManager, and ReflectionGenerator.
    Contributes RAG injections to prompt assembly events and runs periodic reflection generation.
    </summary>
    """

    SUBSCRIPTIONS = {"prompt_assembly": "handle_prompt_assembly"}

    def __init__(self, base_path: str = ".", llm_service: LLMService = None, runtime_state=None):
        """
        <summary>
        Initialise the persistent stores, index, and all collaborators.
        Directories are created if they do not exist.
        </summary>
        <param name="base_path">Root path under which the memories/ directory is created.</param>
        <param name="llm_service">The LLM service forwarded to ReflectionGenerator.</param>
        """
        super().__init__("MemoryService")

        self.runtime_state = runtime_state
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
                chroma_server_http_port=None,
            ),
        )
        db_path = self.sql_dir / "memory_index.db"
        self.conn: Connection = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
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
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_collection_timestamp "
                "ON memory_index (collection, timestamp)"
            )
            self.conn.commit()

    async def _run(self) -> None:
        """
        <summary>
        Background loop that checks for unreflected chat items every 60 seconds
        and generates reflections when the count meets the threshold.
        The check runs immediately on startup so short streams are not missed.
        </summary>
        """
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while not self.app.state.shutdown.is_set():
                self.logger.info("[_run] Checking for reflections...")
                recent_chats = await self.memory_manager.get_recent_items("chat", limit=100, max_age_minutes=120)
                self.logger.info("[_run] Found %s recent chat items", len(recent_chats))
                unreflected = [chat for chat in recent_chats if not chat.get("reflected", False)]
                self.logger.info("[_run] Found %s unreflected items", len(unreflected))

                if len(unreflected) >= REFLECTIONS_THRESHOLD:
                    self.logger.info("[_run] Generating reflections")
                    reflections = await self.memory_manager.generate_reflections()
                    self.logger.info("[_run] Generated %s reflections", len(reflections))
                    for q, a in reflections:
                        await self.memory_manager.add_reflection_item(f"Q: {q}\nA: {a}")
                    ids_to_update = [chat["id"] for chat in unreflected]
                    self.logger.info("[_run] Marking %s items as reflected", len(ids_to_update))
                    await self.memory_manager.update_items_metadata(ids_to_update, {"reflected": True})

                await asyncio.sleep(60)

    async def stop(self) -> None:
        """<summary>Stop the service worker task.</summary>"""
        await super().stop()

    async def add_conversation_item(
        self, role: str, content: str, user_id: str = None, metadata: dict = None
    ) -> None:
        """
        <summary>Persist a conversation turn via MemoryManager.</summary>
        <param name="role">Speaker role string.</param>
        <param name="content">The text content.</param>
        <param name="user_id">Optional user identifier.</param>
        <param name="metadata">Optional metadata dict.</param>
        """
        await self.memory_manager.add_conversation_item(role, content, user_id, metadata=metadata)

    async def get_recent_chat_history(self) -> List[Dict]:
        """<summary>Return the 20 most recent chat items for RAG injection.</summary>"""
        return await self.memory_manager.get_recent_items("chat", limit=20)

    async def get_recent_reflections(self) -> List[Dict]:
        """<summary>Return the 3 most recent reflection Q&A items for RAG injection.</summary>"""
        return await self.memory_manager.get_recent_items("reflections", limit=3)

    def _get_chat_memory_injection(self):
        """<summary>Return a PromptInjection for recent chat history, or None.</summary>"""
        history = self.get_recent_chat_history()
        return chat_memory_module(history)

    def _get_reflection_memory_injection(self):
        """<summary>Return a PromptInjection for recent reflections, or None.</summary>"""
        reflections = self.get_recent_reflections()
        return reflection_memory_module(reflections)

    async def handle_prompt_assembly(self, event: PromptAssemblyEvent) -> None:
        """
        <summary>
        Contribute memory-based injections to a prompt assembly event.
        Appends at most two injections: recent chat history and recent reflections.
        This is the only place MemoryService participates in prompt construction.
        When the memory_read feature flag is disabled, no injections are added so
        the LLM generates without any stored context.
        </summary>
        <param name="event">The PromptAssemblyEvent to contribute injections to.</param>
        """
        if not hasattr(event, "contributions"):
            event.contributions = []

        if self.runtime_state and not self.runtime_state.features.memory_read:
            self.logger.debug("[handle_prompt_assembly] memory_read disabled — skipping RAG injection")
            return

        chat_history = await self.get_recent_chat_history()
        chat_inj = chat_memory_module(chat_history)
        if chat_inj and chat_inj.content:
            event.contributions.append(chat_inj)

        reflections = await self.get_recent_reflections()
        refl_inj = reflection_memory_module(reflections)
        if refl_inj and refl_inj.content:
            event.contributions.append(refl_inj)

        event.contributions.sort(key=lambda inj: inj.priority)