import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.service import Service
from src.qubit.core.events import Event


class DummyService(Service):
    """Concrete test service."""
    SUBSCRIPTIONS = {
        "test_event": "_handle_test",
        "another_event": "_handle_another"
    }

    def __init__(self):
        super().__init__("DummyService")
        self.handled_events = []

    async def _handle_test(self, event: Event):
        self.handled_events.append(event)

    async def _handle_another(self, event: Event):
        self.handled_events.append(event)


@pytest.mark.asyncio
async def test_service_start_registers_subscriptions_and_sets_refs(mock_app, mock_heavy_stack):
    """Demonstrates proper testing of the Service base class with heavy deps mocked."""
    service = DummyService()
    # mock_app from conftest already has event_bus + state

    # Pre-set the start event so _wait_for_start doesn't hang forever
    mock_app.state.start.set()

    await service.start(mock_app)

    assert service.app is mock_app
    assert service.event_bus is mock_app.event_bus
    assert len(service.event_bus.subscribers) >= 2


@pytest.mark.asyncio
async def test_service_stop_cancels_worker(mock_app, mock_heavy_stack):
    service = DummyService()
    mock_app.state.start.set()

    await service.start(mock_app)
    assert service._worker_task is not None

    await service.stop()
    # After stop the task should be cancelled
    assert service._worker_task.cancelled() or service._worker_task.done()
