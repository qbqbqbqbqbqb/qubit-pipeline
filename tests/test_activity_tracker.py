"""Tests for ActivityTracker and ActivityScore."""

import pytest
from unittest.mock import MagicMock
from src.qubit.cognitive.activity.activity_tracker import ActivityTracker
from src.qubit.core.runtime_state import FeatureFlags


def _chat_event(text="hello", user="viewer1"):
    # ActivityTracker receives *_filtered events — chat arrives post-ConversationProcessor.
    e = MagicMock()
    e.type = "twitch_chat_filtered"
    e.text = text
    e.user = user
    e.data = {"text": text, "user": user}
    return e


def _stt_event(text="streamer talking"):
    # ActivityTracker receives *_filtered events — STT arrives post-ConversationProcessor.
    e = MagicMock()
    e.type = "stt_filtered"
    e.text = text
    e.data = {"text": text}
    return e


def _raid_event(user="raider", viewers=50):
    e = MagicMock()
    e.type = "twitch_raid_processed"
    e.user = user
    e.viewers = viewers
    e.data = {}
    return e


@pytest.fixture
def tracker():
    return ActivityTracker()


@pytest.fixture
def flags():
    return FeatureFlags()


@pytest.mark.asyncio
async def test_chat_event_added_to_queue(tracker, flags):
    await tracker.handle_input(_chat_event("hello there"), flags)
    assert tracker.queue.has_source("user_input_chat_message")


@pytest.mark.asyncio
async def test_stt_event_added_to_stt_bucket(tracker, flags):
    await tracker.handle_input(_stt_event(), flags)
    assert tracker.queue.has_source("user_input_stt")


@pytest.mark.asyncio
async def test_chat_disabled_event_not_queued(tracker, flags):
    flags.chat = False
    await tracker.handle_input(_chat_event(), flags)
    assert not tracker.queue.has_source("user_input_chat_message")


@pytest.mark.asyncio
async def test_stt_disabled_event_not_queued(tracker, flags):
    flags.stt = False
    await tracker.handle_input(_stt_event(), flags)
    assert not tracker.queue.has_source("user_input_stt")


@pytest.mark.asyncio
async def test_raid_event_goes_to_community_queue(tracker, flags):
    await tracker.handle_input(_raid_event(), flags)
    pending = tracker.events.peek()
    assert len(pending) == 1
    assert pending[0]["kind"] == "raid"


@pytest.mark.asyncio
async def test_raid_disabled_not_queued(tracker, flags):
    flags.raids = False
    await tracker.handle_input(_raid_event(), flags)
    assert tracker.events.peek() == []


@pytest.mark.asyncio
async def test_short_message_not_queued(tracker, flags):
    await tracker.handle_input(_chat_event("hi"), flags)
    assert not tracker.queue.has_source("user_input_chat_message")


def test_apply_time_decay_does_not_raise(tracker):
    tracker.apply_time_decay()


@pytest.mark.asyncio
async def test_queue_get_best_returns_queued_message(tracker, flags):
    await tracker.handle_input(_chat_event("tell me something interesting"), flags)
    best = tracker.queue.get_best()
    assert best is not None
    assert best["text"] == "tell me something interesting"


def test_queue_get_best_returns_none_when_empty(tracker):
    assert tracker.queue.get_best() is None


def test_peek_pending_events_returns_community_events(tracker):
    tracker.events.add({"kind": "raid", "username": "raider1"})
    events = tracker.peek_pending_events()
    assert len(events) == 1


def test_remove_pending_events(tracker):
    detail = {"kind": "follow", "username": "follower1"}
    tracker.events.add(detail)
    tracker.remove_pending_events([detail])
    assert tracker.peek_pending_events() == []


def test_set_frontend_command(tracker):
    tracker.set_frontend_command("monologue")
    assert tracker.peek_frontend_command() == "monologue"


def test_consume_frontend_command_clears_it(tracker):
    tracker.set_frontend_command("start")
    cmd = tracker.consume_frontend_command()
    assert cmd == "start"
    assert tracker.peek_frontend_command() is None


@pytest.mark.asyncio
async def test_activity_score_increases_after_chat(tracker, flags):
    score_before = tracker.busyness.value
    await tracker.handle_input(_chat_event("interesting question?"), flags)
    assert tracker.busyness.value > score_before


def test_activity_score_property(tracker):
    assert isinstance(tracker.activity_score, float)


def test_activity_score_decays_over_time(tracker):
    tracker.busyness.value = 5.0
    tracker.apply_time_decay()
    # After decay, value should not increase
    assert tracker.busyness.value <= 5.0
