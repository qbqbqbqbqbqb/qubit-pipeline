import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from src.qubit.processing.monologue_input_handler import AutonomousInputHandler
from src.qubit.core.events import Event


@pytest.fixture
def handler():
    mock_prompt = MagicMock()
    mock_prompt.builders = {
        "monologue_prompt": lambda e: MagicMock(),
        "start_message": lambda e: MagicMock()
    }
    mock_prompt.dispatcher = MagicMock()
    mock_prompt.dispatcher.enqueue = AsyncMock()
    mock_memory = MagicMock()
    return AutonomousInputHandler(
        max_age_seconds=30,
        prompt_handler=mock_prompt,
        memory_handler=mock_memory
    )


@pytest.mark.asyncio
async def test_handle_event_drops_stale_message(handler):
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    event = Event(
        type="monologue_prompt",
        timestamp=old_time,
        data={"text": "old monologue"}
    )

    await handler.handle_event(event)
    handler.memory_handler.handle_event.assert_not_called()
    handler.prompt_handler.dispatcher.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_event_processes_fresh_message(handler):
    recent_time = datetime.now(timezone.utc).isoformat()
    event = Event(
        type="monologue_prompt",
        timestamp=recent_time,
        data={"text": "fresh monologue"}
    )

    await handler.handle_event(event)
    handler.memory_handler.handle_event.assert_called_once_with(event)
    handler.prompt_handler.dispatcher.enqueue.assert_awaited_once()
