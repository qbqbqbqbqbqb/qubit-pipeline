import pytest
from src.qubit.core.bootstrap import create_app
from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus as real_event_bus


@pytest.fixture
def mock_bootstrap_heavy(mocker):
    """Patch *all* constructors called by create_app so the test is fast, side-effect-free, and never needs the real ML stack at runtime."""
    mocker.patch("src.qubit.core.bootstrap.ModelManager")
    mocker.patch("src.qubit.core.bootstrap.AsyncHuggingFaceLLM")
    mocker.patch("src.qubit.core.bootstrap.PromptDispatcher")
    mock_mem = mocker.patch("src.qubit.core.bootstrap.MemoryService")
    mock_mem.return_value.name = "MemoryService"
    mocker.patch("src.qubit.core.bootstrap.LLMPromptHandler")
    mocker.patch("src.qubit.core.bootstrap.MemoryHandler")
    mocker.patch("src.qubit.core.bootstrap.TwitchListener")
    mocker.patch("src.qubit.core.bootstrap.TTSHandler")
    mocker.patch("src.qubit.core.bootstrap.OBSHandler")
    mock_out = mocker.patch("src.qubit.core.bootstrap.OutputHandler")
    mock_out.return_value.name = "OutputHandler"
    mocker.patch("src.qubit.core.bootstrap.settings")
    mock_ws = mocker.patch("src.qubit.core.bootstrap.WebSocketServerService")
    mock_ws.return_value.name = "websocket_server"

    # The four EventProcessor-style handlers (we assert the *calls* to register, not real side-effects on the bus)
    mocker.patch("src.qubit.core.bootstrap.ModerationHandler")
    mocker.patch("src.qubit.core.bootstrap.InputHandler")
    mocker.patch("src.qubit.core.bootstrap.AutonomousInputHandler")
    mocker.patch("src.qubit.core.bootstrap.FrontendCommandHandler")


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


@pytest.mark.asyncio
async def test_create_app_registers_event_subscriptions(mock_bootstrap_heavy):
    """
    Verify that the EventProcessor-style handlers are instantiated and have register_subscriptions called.
    """
    app = await create_app()

    # Because we fully mock the four handlers, we assert that the wiring code called register on each
    # (the real implementations are unit-tested elsewhere).
    from src.qubit.core.bootstrap import (
        ModerationHandler,
        InputHandler,
        AutonomousInputHandler,
        FrontendCommandHandler,
    )
    ModerationHandler.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    InputHandler.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    AutonomousInputHandler.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
    FrontendCommandHandler.return_value.register_subscriptions.assert_called_once_with(real_event_bus)
