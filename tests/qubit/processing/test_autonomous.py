import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from src.qubit.processing.autonomous import AutonomousPromptProcessor
from src.qubit.core.events import Event


@pytest.fixture
def handler():
    mock_memory = AsyncMock()
    mock_bus = AsyncMock()
    return AutonomousPromptProcessor(
        max_age_seconds=30,
        memory_writer=mock_memory,
        event_bus=mock_bus
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
    handler.memory_writer.handle_event.assert_not_called()
    handler.event_bus.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_event_processes_fresh_message(handler):
    recent_time = datetime.now(timezone.utc).isoformat()
    event = Event(
        type="monologue_prompt",
        timestamp=recent_time,
        data={"text": "fresh monologue"}
    )

    await handler.handle_event(event)
    handler.memory_writer.handle_event.assert_called_once_with(event)
    handler.event_bus.publish.assert_awaited_once()
