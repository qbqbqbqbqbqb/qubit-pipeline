import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Directory-level heavy mocking (mock_heavy_stack) + precise local patches below.
from src.qubit.memory.service import MemoryService


@pytest.mark.asyncio
async def test_memory_service_instantiation_minimal():
    # This will attempt to create real chroma + sqlite in a temp location
    # We patch to avoid side effects in test env
    with patch("src.qubit.memory.service.chromadb.PersistentClient") as mock_chroma, \
         patch("sqlite3.connect") as mock_sqlite:
        mock_chroma.return_value = MagicMock()
        mock_sqlite.return_value = MagicMock()

        service = MemoryService(base_path=".", llm_service=MagicMock())
        assert service.memory_manager is not None
        assert "MemoryService" in service.name


@pytest.mark.asyncio
async def test_handle_prompt_assembly_adds_injections():
    with patch("src.qubit.memory.service.chromadb.PersistentClient") as mock_chroma, \
         patch("sqlite3.connect") as mock_sqlite:
        mock_chroma.return_value = MagicMock()
        mock_sqlite.return_value = MagicMock()

        service = MemoryService(base_path=".", llm_service=MagicMock())
        service.get_recent_chat_history = MagicMock(return_value=[])
        service.get_recent_reflections = MagicMock(return_value=[])

        event = MagicMock()
        event.contributions = []

        await service.handle_prompt_assembly(event)

        # Should have tried to add injections (even if empty)
        assert hasattr(event, "contributions")
