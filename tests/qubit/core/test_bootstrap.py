import pytest

pytest.importorskip("twitchAPI", reason="bootstrap test requires full dependency stack (twitchAPI, torch, etc.)")

from src.qubit.core.bootstrap import create_app
from src.qubit.core.app import App
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import event_bus as real_event_bus


@pytest.mark.asyncio
async def test_create_app_returns_properly_wired_app():
    """
    Integration-style test for the application factory.

    This test exercises the real create_app() wiring.
    It will only pass in an environment that has the full dependency set
    (twitchAPI, chromadb, torch, etc.) installed.
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
async def test_create_app_registers_event_subscriptions():
    """
    Verify that the EventProcessor-style handlers register their subscriptions.
    """
    app = await create_app()

    # After create_app, several handlers should have subscribed to the bus
    # We can check by looking at the event_bus subscriber counts for known events
    # (or simply that subscriptions happened)
    assert len(app.event_bus.subscribers) > 0
