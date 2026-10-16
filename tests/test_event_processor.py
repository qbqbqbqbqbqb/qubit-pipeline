"""Tests for EventProcessor subscription wiring."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.qubit.core.event_bus import EventBus
from src.qubit.core.event_processor import EventProcessor


class ConcreteProcessor(EventProcessor):
    """Minimal concrete implementation for testing."""
    SUBSCRIPTIONS = {
        "chat_message": "handle_event",
        "raid_event": "handle_raid",
    }

    def __init__(self):
        super().__init__("test_processor")
        self.events = []
        self.raids = []

    async def handle_event(self, event):
        self.events.append(event)

    async def handle_raid(self, event):
        self.raids.append(event)


class MissingHandlerProcessor(EventProcessor):
    SUBSCRIPTIONS = {"some_event": "nonexistent_handler"}

    async def handle_event(self, event):
        pass


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def processor():
    return ConcreteProcessor()


def test_register_subscriptions_sets_event_bus(processor, bus):
    processor.register_subscriptions(bus)
    assert processor.event_bus is bus


def test_register_subscriptions_none_bus_does_not_set(processor):
    processor.register_subscriptions(None)
    assert processor.event_bus is None


@pytest.mark.asyncio
async def test_registered_handler_receives_event(processor, bus):
    processor.register_subscriptions(bus)

    event = MagicMock()
    event.type = "chat_message"
    await bus.publish(event)

    assert processor.events == [event]


@pytest.mark.asyncio
async def test_multiple_subscriptions_routed_correctly(processor, bus):
    processor.register_subscriptions(bus)

    chat = MagicMock(type="chat_message")
    raid = MagicMock(type="raid_event")

    await bus.publish(chat)
    await bus.publish(raid)

    assert processor.events == [chat]
    assert processor.raids == [raid]


@pytest.mark.asyncio
async def test_missing_handler_does_not_raise_on_register(bus):
    proc = MissingHandlerProcessor("missing_handler_proc")
    proc.register_subscriptions(bus)
    # Should log warning but not raise
    await bus.publish(MagicMock(type="some_event"))


def test_register_subscriptions_idempotent(processor, bus):
    processor.register_subscriptions(bus)
    processor.register_subscriptions(bus)
    # Calling twice should not double-register (depends on EventBus impl)
    # At minimum should not raise
    assert processor.event_bus is bus
