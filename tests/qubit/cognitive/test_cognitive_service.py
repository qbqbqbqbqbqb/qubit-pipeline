import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.qubit.cognitive.cognitive_service import CognitiveService
from src.qubit.core.events import Event


@pytest.mark.asyncio
async def test_cognitive_service_initialization():
    service = CognitiveService(inactivity_timeout=60)
    assert service.inactivity_timeout == 60
    assert service.tracker is not None
    assert service.engine is not None


@pytest.mark.asyncio
async def test_handle_input_routes_to_tracker(mock_app):
    service = CognitiveService()
    service.app = mock_app
    service.tracker.handle_input = AsyncMock()

    event = Event(type="twitch_chat_processed", timestamp="now", data={"text": "hello there"})

    await service._handle_input(event)
    service.tracker.handle_input.assert_awaited_once()


@pytest.mark.asyncio
async def test_toggle_monologue_updates_features(mock_app):
    service = CognitiveService()
    service.app = mock_app
    mock_app.state.features = {"monologue": True}

    service.toggle_monologue(False)
    assert mock_app.state.features["monologue"] is False


@pytest.mark.asyncio
async def test_frontend_command_handling(mock_app):
    service = CognitiveService()
    service.app = mock_app

    event = Event(
        type="frontend_command",
        timestamp="now",
        data={"command": "start"}
    )

    await service._handle_frontend_command(event)
    assert service.get_current_frontend_command() == "start"
    # second call should clear it
    assert service.get_current_frontend_command() is None
