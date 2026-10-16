"""Tests for core EventBus pub/sub behaviour."""

import pytest
from src.qubit.core.event_bus import EventBus
from src.qubit.core.events import Event


def _evt(type_="test_event"):
    return Event(type=type_, timestamp="2026-01-01T00:00:00+00:00", data={})


@pytest.mark.asyncio
async def test_async_handler_called():
    bus = EventBus()
    received = []

    async def handler(e):
        received.append(e)

    bus.subscribe("test_event", handler)
    ev = _evt("test_event")
    await bus.publish(ev)

    assert received == [ev]


@pytest.mark.asyncio
async def test_sync_handler_called():
    bus = EventBus()
    received = []

    def handler(e):
        received.append(e)

    bus.subscribe("test_event", handler)
    await bus.publish(_evt("test_event"))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_no_subscribers_does_not_raise():
    bus = EventBus()
    await bus.publish(_evt("orphan_event"))


@pytest.mark.asyncio
async def test_multiple_handlers_all_called():
    bus = EventBus()
    calls = []

    async def h1(e): calls.append("h1")
    async def h2(e): calls.append("h2")

    bus.subscribe("ev", h1)
    bus.subscribe("ev", h2)
    await bus.publish(_evt("ev"))

    assert calls == ["h1", "h2"]


@pytest.mark.asyncio
async def test_failing_handler_does_not_block_subsequent_handlers():
    bus = EventBus()
    calls = []

    async def bad(e): raise ValueError("boom")
    async def good(e): calls.append("good")

    bus.subscribe("ev", bad)
    bus.subscribe("ev", good)
    await bus.publish(_evt("ev"))

    assert calls == ["good"]


@pytest.mark.asyncio
async def test_wrong_event_type_not_delivered():
    bus = EventBus()
    received = []

    async def handler(e): received.append(e)

    bus.subscribe("type_a", handler)
    await bus.publish(_evt("type_b"))

    assert received == []


@pytest.mark.asyncio
async def test_multiple_event_types_routed_correctly():
    bus = EventBus()
    a_calls, b_calls = [], []

    async def on_a(e): a_calls.append(e)
    async def on_b(e): b_calls.append(e)

    bus.subscribe("type_a", on_a)
    bus.subscribe("type_b", on_b)

    await bus.publish(_evt("type_a"))
    await bus.publish(_evt("type_b"))

    assert len(a_calls) == 1
    assert len(b_calls) == 1
