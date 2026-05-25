"""
Example of a well-structured integration-style test for a complex wiring factory.

Follows the guidelines in tests/AGENTS.md:
- Uses the shared mock_heavy_stack + a specific local fixture
- Lazy / mocked construction to avoid real ML / external dependencies
- Clear assertions on the resulting object graph
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.bootstrap import create_app
from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus as real_event_bus



@pytest.fixture
def mock_bootstrap_heavy(mocker, mock_heavy_stack):
    """Specific wiring mocks on top of the broad mock_heavy_stack.
    
    The shared fixture handles the heavy scientific / external packages.
    This fixture focuses on the exact constructors used inside create_app().
    """
    mock_llm_service = mocker.patch("src.qubit.core.bootstrap.LLMService")
    # Make the instance support the async methods called in create_app
    mock_instance = mock_llm_service.return_value
    mock_instance.register_profile = MagicMock()
    mock_instance.ensure_loaded = AsyncMock()
    mock_instance.generate_with_retries = AsyncMock(return_value="mock response")

    mocker.patch("src.qubit.core.bootstrap.GenerationCoordinator")
    mock_mem =     mocker.patch("src.qubit.core.bootstrap.MemoryService")
    mock_mem.return_value.name = "MemoryService"
    mocker.patch("src.qubit.core.bootstrap.ModerationProcessor")
    mocker.patch("src.qubit.core.bootstrap.FrontendCommandProcessor")
    mocker.patch("src.qubit.core.bootstrap.ConversationProcessor")
    mocker.patch("src.qubit.core.bootstrap.AutonomousPromptProcessor")


@pytest.mark.asyncio
async def test_create_app_returns_properly_wired_app(mock_bootstrap_heavy):
    """
    Test that create_app wires the core components correctly (using mocks for heavy deps).
    """
    app = await create_app()

    assert isinstance(app, App)
    assert isinstance(app.state, RuntimeState)
    assert app.event_bus is real_event_bus

    # Core services that are always added
    service_names = [getattr(s, "name", type(s).__name__) for s in app.services]
    assert any("websocket" in n.lower() for n in service_names)
    assert any("memory" in n.lower() for n in service_names)
    assert len(app.services) >= 6
    # Also verify that the real global event bus was attached (not a mock)
    assert app.event_bus is real_event_bus


@pytest.mark.asyncio
async def test_create_app_registers_event_subscriptions(mock_bootstrap_heavy, mock_heavy_stack):
    """
    Verify that the EventProcessor-style handlers are instantiated and have register_subscriptions called.
    """
    app = await create_app()

    # Because we fully mock the four handlers, we assert that the wiring code called register on each
    # (the real implementations are unit-tested elsewhere).
    from src.qubit.core.bootstrap import (
        ModerationProcessor,
        ConversationProcessor,
        AutonomousPromptProcessor,
        FrontendCommandProcessor,
    )
    ModerationProcessor.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    ConversationProcessor.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    AutonomousPromptProcessor.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    FrontendCommandProcessor.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
