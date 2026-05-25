import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from src.qubit.processing.input_handler import InputHandler
from src.qubit.core.events import Event


@pytest.fixture
def input_handler():
    mock_prompt = MagicMock()
    mock_memory = MagicMock()
    handler = InputHandler(
        max_age_seconds=30,
        prompt_handler=mock_prompt,
        memory_handler=mock_memory
    )
    handler.event_bus = AsyncMock()
    handler.logger = MagicMock()
    return handler


@pytest.mark.asyncio
async def test_input_handler_drops_stale_messages(input_handler, mock_heavy_stack):
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    event = Event(
        type="twitch_chat_processed",
        timestamp=old_time,
        data={"text": "old message"}
    )

    await input_handler.handle_event(event)
    # Should have returned early, no memory handling
    input_handler.memory_handler.handle_event.assert_not_called()


@pytest.mark.asyncio
async def test_input_handler_processes_fresh_message(input_handler, mock_heavy_stack):
    recent_time = datetime.now(timezone.utc).isoformat()
    event = Event(
        type="twitch_chat_processed",
        timestamp=recent_time,
        data={"text": "fresh and unique message here"}
    )

    await input_handler.handle_event(event)
    input_handler.memory_handler.handle_event.assert_called_once_with(event)
