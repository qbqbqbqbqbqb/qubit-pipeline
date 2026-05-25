import pytest
from unittest.mock import MagicMock

# This directory is marked heavy + usefixtures("mock_heavy_stack") in conftest.py.
# Local fixtures below provide precise injection for MemoryManager.
from src.qubit.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_chroma_client():
    client = MagicMock()
    chat_coll = MagicMock()
    refl_coll = MagicMock()
    client.get_or_create_collection.side_effect = lambda name, **kwargs: (
        chat_coll if "chat" in name else refl_coll
    )
    return client


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    conn.execute.return_value = cursor
    return conn


def test_memory_manager_initializes_collections(mock_chroma_client, mock_conn):
    mm = MemoryManager(chroma_client=mock_chroma_client, conn=mock_conn)
    assert "chat" in mm.collections
    assert "reflections" in mm.collections


def test_get_recent_items_invalid_collection_raises(mock_chroma_client, mock_conn):
    mm = MemoryManager(chroma_client=mock_chroma_client, conn=mock_conn)
    with pytest.raises(ValueError):
        mm.get_recent_items("invalid_collection")


def test_update_items_metadata_does_not_crash(mock_chroma_client, mock_conn):
    mm = MemoryManager(chroma_client=mock_chroma_client, conn=mock_conn)
    # Should not raise even if chroma behaves minimally
    mm.update_items_metadata(["id1"], {"reflected": True})


@pytest.mark.asyncio
async def test_generate_reflections_returns_empty_when_no_generator(mock_chroma_client, mock_conn):
    mm = MemoryManager(chroma_client=mock_chroma_client, conn=mock_conn, reflections_generator=None)
    with pytest.raises(ValueError):
        await mm.generate_reflections()
