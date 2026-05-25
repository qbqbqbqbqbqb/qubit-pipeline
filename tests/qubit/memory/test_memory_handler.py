import pytest
from unittest.mock import MagicMock

from src.qubit.memory.memory_handler import MemoryHandler
from src.qubit.core.events import Event


@pytest.fixture
def mock_memory_service():
    return MagicMock()


@pytest.fixture
def memory_handler(mock_memory_service):
    return MemoryHandler(mock_memory_service)


def test_memory_handler_routes_chat_event(memory_handler, mock_memory_service):
    event = MagicMock()
    event.type = "twitch_chat_processed"
    event.text = "hello world"
    event.user = "viewer123"
    event.timestamp = "2026-05-25T00:00:00Z"

    memory_handler.handle_event(event)

    mock_memory_service.add_conversation_item.assert_called_once_with(
        "User", "hello world", user_id="viewer123",
        metadata={"source": "chat", "timestamp": "2026-05-25T00:00:00Z"}
    )


def test_memory_handler_routes_response_event(memory_handler, mock_memory_service):
    event = MagicMock()
    event.type = "response_generated"
    event.response = "That's funny!"
    event.timestamp = "2026-05-25T00:00:00Z"

    memory_handler.handle_event(event)

    mock_memory_service.add_conversation_item.assert_called_once_with(
        "Qubit", "That's funny!",
        metadata={"source": "response", "timestamp": "2026-05-25T00:00:00Z"}
    )


def test_memory_handler_routes_monologue_event(memory_handler, mock_memory_service):
    event = MagicMock()
    event.type = "monologue_prompt"
    event.prompt = "Talk about AI"
    event.timestamp = "2026-05-25T00:00:00Z"

    memory_handler.handle_event(event)

    mock_memory_service.add_conversation_item.assert_called_once_with(
        "System", "Talk about AI",
        metadata={"source": "monologue", "timestamp": "2026-05-25T00:00:00Z"}
    )


def test_memory_handler_ignores_unknown_event(memory_handler, mock_memory_service):
    event = MagicMock()
    event.type = "some_random_event"

    memory_handler.handle_event(event)

    mock_memory_service.add_conversation_item.assert_not_called()
