import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.qubit.core.runtime import run_app
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_run_app_starts_services_and_waits_for_start():
    app = MagicMock()
    app.services = []
    app.state = RuntimeState()
    app.event_bus = EventBus()

    # Pre-signal the start so we don't hang
    app.state.start.set()

    # run_app will hit the shutdown wait, so we also set shutdown quickly
    async def trigger_shutdown():
        await asyncio.sleep(0.01)
        app.state.shutdown.set()

    asyncio.create_task(trigger_shutdown())

    # Should not raise
    await run_app(app)


@pytest.mark.asyncio
async def test_run_app_with_real_service_mocks():
    svc = MagicMock()
    svc.start = AsyncMock()
    svc.stop = AsyncMock()

    app = MagicMock()
    app.services = [svc]
    app.state = RuntimeState()
    app.event_bus = EventBus()

    app.state.start.set()

    async def trigger_shutdown():
        await asyncio.sleep(0.01)
        app.state.shutdown.set()

    asyncio.create_task(trigger_shutdown())

    await run_app(app)

    # start is called inside the run_app loop
    svc.start.assert_awaited_once()
