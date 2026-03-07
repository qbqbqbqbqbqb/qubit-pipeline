import asyncio
from pathlib import Path
from typing import Dict
import chromadb

from chromadb.config import Settings
from src.qubit.core.events import PromptAssemblyEvent
from src.qubit.prompting.modules.chat import chat_memory_module
from src.qubit.prompting.modules.reflection import reflection_memory_module
from src.qubit.core.service import Service
from src.qubit.memory.memory_manager import MemoryManager
from src.utils.log_utils import get_logger


class MemoryService(Service):
    SUBSCRIPTIONS = {"prompt_assembly": "handle_prompt_assembly"}

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
        
        self.memory_manager = MemoryManager(self.chroma_client, dispatcher=None)

    async def start(self, app):
        self.logger.info("MemoryService started")
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        await super().start(app)

    async def _worker(self):
        REFLECTIONS_THRESHOLD = 20
        while self._running:
            await asyncio.sleep(60)
            recent_chats = self.memory_manager.get_recent_items("chat", limit=100, max_age_minutes=120)
            unreflected = [chat for chat in recent_chats if not chat.get("reflected", False)]
            if len(unreflected) >= REFLECTIONS_THRESHOLD:
                self.logger.info("creating reflection")
                reflections = await self.memory_manager.generate_reflections()
                for q, a in reflections:
                    self.memory_manager.add_reflection_item(f"Q: {q}\nA: {a}")
                ids_to_update = [chat["id"] for chat in unreflected] 
                self.memory_manager.update_items_metadata(ids_to_update, {"reflected": True})

    async def stop(self):
        self.logger.info("MemoryService stopped")
        await super().stop()

    def add_conversation_item(self, role: str, content: str, user_id: str = None, metadata: dict = None) -> None:
        """
        Add a conversation item to the chat history.
        """
        self.memory_manager.add_conversation_item(role, content, user_id, metadata=metadata)

    def get_recent_chat_history(self):
        return self.memory_manager.get_recent_items("chat", limit=20)

    def get_recent_reflections(self):
        return self.memory_manager.get_recent_items("reflections", limit=3)
        
    async def handle_prompt_assembly(self, event: PromptAssemblyEvent):
        if not hasattr(event, "contributions"):
            event.contributions = []
    
        chat_injection = chat_memory_module(self.get_recent_chat_history())
        reflection_injection = reflection_memory_module(self.get_recent_reflections())

        if chat_injection and chat_injection.content:
            event.contributions.append(chat_injection)

        if reflection_injection and reflection_injection.content:
            event.contributions.append(reflection_injection)

        event.contributions.sort(key=lambda inj: inj.priority)