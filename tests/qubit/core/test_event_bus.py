import pytest
from src.qubit.core.event_bus import EventBus
from src.qubit.core.events import Event
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_subscribe_and_publish(event_bus, sample_event, mock_heavy_stack):
    received = []

    async def handler(event):
        received.append(event)

    event_bus.subscribe("test_event", handler)
    await event_bus.publish(sample_event)

    assert len(received) == 1
    assert received[0].type == "test_event"


@pytest.mark.asyncio
async def test_multiple_subscribers(event_bus, mock_heavy_stack):
    calls = []

    async def async_handler(e):
        calls.append("async")

    def sync_handler(e):
        calls.append("sync")

    event_bus.subscribe("multi", async_handler)
    event_bus.subscribe("multi", sync_handler)

    event = Event(type="multi", timestamp="now", data={})
    await event_bus.publish(event)

    assert "async" in calls
    assert "sync" in calls


@pytest.mark.asyncio
async def test_publish_no_subscribers_does_not_crash(event_bus, mock_heavy_stack):
    event = Event(type="unknown", timestamp="now", data={})
    await event_bus.publish(event)  # Should not raise


@pytest.mark.asyncio
async def test_handler_error_is_caught_and_logged(event_bus, mocker, mock_heavy_stack):
    error_logger = mocker.patch("src.qubit.core.event_bus.logger.error")

    def bad_handler(e):
        raise ValueError("Handler crashed!")

    event_bus.subscribe("bad", bad_handler)
    event = Event(type="bad", timestamp="now", data={})

    await event_bus.publish(event)  # Should catch error
    error_logger.assert_called_once()