"""
Integration tests for the application bootstrap factory (create_app).

This test verifies that the central wiring function in src/qubit/core/bootstrap.py
correctly instantiates and connects all layers according to the target architecture:

- Core runtime components (App, RuntimeState, EventBus)
- Models layer (LLMService + profiles)
- Generation layer (GenerationCoordinator)
- Memory layer (MemoryService + MemoryWriter)
- Input Processing layer (Moderation, Conversation, Autonomous processors)
- Cognitive layer (CognitiveOrchestrator)
- Output layer (OutputCoordinator)
- Input sources (TwitchListener)
- Infrastructure (WebSocketServerService)

The tests use heavy mocking (via mock_heavy_stack and local fixture) to avoid
loading real ML models, databases, or external services during collection and execution.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.bootstrap import create_app
from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus as real_event_bus



@pytest.fixture
def mock_bootstrap_heavy(mocker, mock_heavy_stack):
    """
    Mocks the constructors of all major components instantiated inside create_app().

    This allows the test to verify the wiring logic without actually constructing
    real LLM services, memory systems, or external listeners.

    The fixture:
    - Mocks LLMService and configures its async methods
    - Mocks GenerationCoordinator, MemoryService, and the four main EventProcessors
    - Relies on the shared mock_heavy_stack for torch/transformers/chromadb/etc.
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
    Verifies that create_app produces a correctly structured App instance.

    Assertions check:
    - The returned object is an App with proper RuntimeState and real EventBus
    - Core services (websocket, memory, generation) are registered for lifecycle management
    - At least 6 services are present (infrastructure + major layers)
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
    Verifies that pure EventProcessors are wired to the EventBus via register_subscriptions.

    This test imports the classes from bootstrap (which are the mocked versions) and
    asserts that the wiring code in create_app correctly calls register_subscriptions
    on ModerationProcessor, ConversationProcessor, AutonomousPromptProcessor, and
    FrontendCommandProcessor.

    The real implementations of these processors are tested in their own unit tests.
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
