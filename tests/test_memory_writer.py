"""Tests for MemoryWriter event routing."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from src.qubit.core.event_bus import EventBus
from src.qubit.memory.writer import MemoryWriter


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _event(type_, **kwargs):
    e = MagicMock()
    e.type = type_
    e.timestamp = _ts()
    e.data = kwargs
    for k, v in kwargs.items():
        setattr(e, k, v)
    return e


@pytest.fixture
def memory_service():
    svc = MagicMock()
    svc.add_conversation_item = AsyncMock()
    return svc


@pytest.fixture
def writer(memory_service):
    return MemoryWriter(memory_service, stt_speaker_name="Streamer")


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def wired_writer(writer, bus):
    writer.register_subscriptions(bus)
    return writer


async def test_chat_event_calls_add_conversation_item(wired_writer, bus, memory_service):
    await bus.publish(_event("twitch_chat_processed", user="viewer1", text="hello"))
    memory_service.add_conversation_item.assert_called_once()
    args = memory_service.add_conversation_item.call_args
    assert args.kwargs.get("role") == "User" or args.args[0] == "User"


async def test_stt_event_stored_as_user_role(wired_writer, bus, memory_service):
    await bus.publish(_event("stt_processed", text="I said something", user="streamer"))
    memory_service.add_conversation_item.assert_called_once()
    call_args = memory_service.add_conversation_item.call_args
    role = call_args.args[0] if call_args.args else call_args.kwargs.get("role")
    assert role == "User"


async def test_response_event_stored_as_qubit_role(wired_writer, bus, memory_service):
    await bus.publish(_event("response_generated", response="I replied", source="chat", prompt="hello"))
    memory_service.add_conversation_item.assert_called_once()
    call_args = memory_service.add_conversation_item.call_args
    role = call_args.args[0] if call_args.args else call_args.kwargs.get("role")
    assert role == "Qubit"


async def test_monologue_event_stored(wired_writer, bus, memory_service):
    await bus.publish(_event("monologue_prompt", prompt="say something fun", label="self_aware"))
    memory_service.add_conversation_item.assert_called_once()


async def test_unsubscribed_event_type_not_stored(wired_writer, bus, memory_service):
    await bus.publish(_event("some_other_event", text="ignored"))
    memory_service.add_conversation_item.assert_not_called()


async def test_subscription_event_stored(wired_writer, bus, memory_service):
    await bus.publish(_event("twitch_subscription_processed", user="subber", tier="1000", sub_type="prime"))
    memory_service.add_conversation_item.assert_called_once()


async def test_follow_event_stored(wired_writer, bus, memory_service):
    await bus.publish(_event("twitch_follow_processed", user="follower1"))
    memory_service.add_conversation_item.assert_called_once()


async def test_kick_chat_event_stored(wired_writer, bus, memory_service):
    await bus.publish(_event("kick_chat_processed", user="kickviewer", text="hi from kick"))
    memory_service.add_conversation_item.assert_called_once()


async def test_writer_without_bus_does_not_crash(writer, memory_service):
    # Not registered on any bus — direct handle_event call should still work
    event = _event("twitch_chat_processed", user="viewer1", text="hello")
    await writer.handle_event(event)
    memory_service.add_conversation_item.assert_called_once()
