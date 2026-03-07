import asyncio
from pathlib import Path
from typing import Dict
import chromadb

from chromadb.config import Settings
from src.qubit.memory.reflections_manager import ReflectionsManager
from src.qubit.core.service import Service
from src.qubit.memory.chat_history import ChatHistoryManager
from src.utils.log_utils import get_logger


class MemoryService(Service):
    def __init__(self, base_path: str = "."):
        self.logger = get_logger(__name__)
        super().__init__("MemoryService")
    
        self.base_path = Path(base_path)
        self.memories_dir = self.base_path / "memories"
        self.memories_dir.mkdir(exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
        path=str(self.base_path / "memories" / "chroma.db"),
        settings=Settings(
            anonymized_telemetry=False,
            chroma_server_host=None,
            chroma_server_http_port=None
        )
    )
        
        self.chat_history_manager = ChatHistoryManager(self.chroma_client, "conversation_collection")
        self.reflections_manager = ReflectionsManager(self.chroma_client, "reflections_collection")
        
    async def start(self, app):
        self.logger.info("MemoryService started")
        self._running = True
        self._worker_task = asyncio.create_task(self._worker(app))
        await super().start(app)

    async def _worker(self, app):
        REFLECTIONS_THRESHOLD = 20 
        while self._running:
            await asyncio.sleep(60)
            conversation_count = self.chat_history_manager.get_recent_chat_history(limit=100)
            if len(conversation_count) >= REFLECTIONS_THRESHOLD:
                self.reflections_manager.create_reflection() # add reflected marker

    async def stop(self):
        self.logger.info("MemoryService stopped")
        await super().stop()

    def add_conversation_item(self, role: str, content: str, user_id: str = None) -> None:
        """
        Add a conversation item to the chat history.
        """
        self.chat_history_manager.add_conversation_item_sync(role, content, user_id)

    def get_recent_chat_history(self):
        self.chat_history_manager.get_recent_chat_history(limit=20)

    def get_recent_reflections(self):
        pass