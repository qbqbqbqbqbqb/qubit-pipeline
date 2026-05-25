import pytest
from unittest.mock import AsyncMock, MagicMock
from src.qubit.input.frontend_command_handler import FrontendCommandHandler
from src.qubit.core.events import Event


@pytest.mark.asyncio
async def test_frontend_command_handler_normalizes_bot_started(mock_heavy_stack):
    handler = FrontendCommandHandler()
    handler.event_bus = AsyncMock()
    handler.logger = MagicMock()  # EventProcessor sets it via super

    event = Event(
        type="bot_started",
        timestamp="now",
        data={"command": "bot_started"}
    )

    await handler.handle_event(event)

    handler.event_bus.publish.assert_awaited_once()
    published = handler.event_bus.publish.call_args[0][0]
    assert published.type == "frontend_command"
    assert published.data["command"] == "start"
    assert published.data["source"] == "frontend"
