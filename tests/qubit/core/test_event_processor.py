import pytest
from unittest.mock import MagicMock
from src.qubit.core.event_processor import EventProcessor
from src.qubit.core.events import Event


class ConcreteProcessor(EventProcessor):
    SUBSCRIPTIONS = {
        "test_event": "handle_event"
    }

    def __init__(self):
        super().__init__("ConcreteProcessor")
        self.received = []

    async def handle_event(self, event):
        self.received.append(event)


def test_event_processor_is_abstract():
    with pytest.raises(TypeError):
        EventProcessor("abstract")  # can't instantiate ABC without impl


@pytest.mark.asyncio
async def test_register_subscriptions_attaches_to_bus():
    proc = ConcreteProcessor()
    bus = MagicMock()

    proc.register_subscriptions(bus)

    assert proc.event_bus is bus
    bus.subscribe.assert_called_once_with("test_event", proc.handle_event)
