"""Tests for ModerationProcessor, ConversationProcessor, AutonomousPromptProcessor."""

import pytest
import dataclasses
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from src.qubit.core.event_bus import EventBus
from src.qubit.core.events import (
    TwitchChatEvent, TwitchRaidEvent, TwitchFollowEvent, TwitchSubscriptionEvent,
    KickChatEvent, KickRaidEvent,
)
from src.qubit.processing.moderation import ModerationProcessor
from src.qubit.processing.conversation import ConversationProcessor
from src.qubit.processing.autonomous import AutonomousPromptProcessor


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _raw_twitch_chat(text="hello", user="viewer1"):
    return TwitchChatEvent(
        type="twitch_chat", timestamp=_ts(),
        data={"text": text, "user": user}, user=user, text=text,
    )


def _raw_kick_chat(text="hello", user="viewer1"):
    return KickChatEvent(
        type="kick_chat", timestamp=_ts(),
        data={"text": text, "user": user}, user=user, text=text,
    )


def _raw_twitch_raid(user="raider", viewers=100):
    return TwitchRaidEvent(
        type="twitch_raid", timestamp=_ts(),
        data={}, user=user, viewers=viewers,
    )


def _raw_kick_raid(user="raider", viewers=50):
    return KickRaidEvent(
        type="kick_raid", timestamp=_ts(),
        data={}, user=user, viewers=viewers,
    )


def _processed_twitch_chat(text="hello", user="viewer1"):
    """Return a real TwitchChatEvent with *_processed type for ConversationProcessor tests."""
    return TwitchChatEvent(
        type="twitch_chat_processed", timestamp=_ts(),
        data={"text": text, "user": user}, user=user, text=text,
    )


def _processed_stt(text="hello", user="streamer"):
    """Return a real dataclass-based STT event mock for ConversationProcessor tests."""
    # STT events share the same fields as TwitchChatEvent for test purposes.
    return TwitchChatEvent(
        type="stt_processed", timestamp=_ts(),
        data={"text": text, "user": user}, user=user, text=text,
    )


def _monologue_event(prompt="talk about something"):
    e = MagicMock()
    e.type = "monologue_prompt"
    e.prompt = prompt
    e.timestamp = _ts()
    e.data = {"prompt": prompt, "label": "self_aware", "user": "system"}
    return e


# -----------------------------------------------------------------------
# ModerationProcessor
# -----------------------------------------------------------------------

class TestModerationProcessor:
    """
    ModerationProcessor subscribes to raw platform events (twitch_chat,
    kick_chat, twitch_raid, etc.), sanitises them, and publishes *_processed
    variants on the bus.
    """

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def processor(self, bus):
        p = ModerationProcessor()
        p.register_subscriptions(bus)
        return p

    async def test_twitch_chat_published_as_processed(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_processed", capture)

        await processor.handle_event(_raw_twitch_chat())

        assert any(e.type == "twitch_chat_processed" for e in published)

    async def test_kick_chat_published_as_processed(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("kick_chat_processed", capture)

        await processor.handle_event(_raw_kick_chat())

        assert any(e.type == "kick_chat_processed" for e in published)

    async def test_twitch_raid_published_as_processed(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_raid_processed", capture)

        await processor.handle_event(_raw_twitch_raid())

        assert any(e.type == "twitch_raid_processed" for e in published)

    async def test_kick_raid_published_as_processed(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("kick_raid_processed", capture)

        await processor.handle_event(_raw_kick_raid())

        assert any(e.type == "kick_raid_processed" for e in published)

    async def test_blacklisted_word_filtered(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_processed", capture)

        # "badword" is in the stub blacklisted_words.txt loaded at import time
        await processor.handle_event(_raw_twitch_chat(text="this has badword in it"))

        assert not any(e.type == "twitch_chat_processed" for e in published)

    async def test_unknown_event_type_logs_warning_does_not_raise(self, processor):
        e = MagicMock()
        e.type = "totally_unknown_event"
        e.timestamp = _ts()
        e.data = {}
        await processor.handle_event(e)  # should not raise


# -----------------------------------------------------------------------
# ConversationProcessor
# -----------------------------------------------------------------------

class TestConversationProcessor:
    """
    ConversationProcessor deduplicates and age-filters *_processed chat/stt
    events, then re-publishes survivors as *_filtered events.
    Downstream consumers (CognitiveOrchestrator, MemoryWriter) subscribe to
    *_filtered, so this processor is the real gatekeeper.
    """

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def processor(self, bus):
        p = ConversationProcessor(max_age_seconds=30)
        p.register_subscriptions(bus)
        return p

    async def test_fresh_event_published_as_filtered(self, processor, bus):
        """A fresh, unique event must be re-published with the *_filtered type."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_filtered", capture)

        await processor.handle_event(_processed_twitch_chat())

        assert len(published) == 1
        assert published[0].type == "twitch_chat_filtered"

    async def test_stale_event_not_published(self, processor, bus):
        """An event with an old timestamp must be dropped and nothing published."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_filtered", capture)

        stale = _processed_twitch_chat()
        stale = dataclasses.replace(stale, timestamp="2020-01-01T00:00:00+00:00")
        await processor.handle_event(stale)

        assert not published

    async def test_duplicate_message_not_published(self, processor, bus):
        """A second identical message must be dropped by the dedup filter."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_filtered", capture)

        await processor.handle_event(_processed_twitch_chat(text="same message here"))
        published.clear()
        await processor.handle_event(_processed_twitch_chat(text="same message here"))

        assert not published

    async def test_fresh_unique_message_not_repeated(self, processor):
        """A message that has never been seen must not be flagged as repeated."""
        assert processor._is_repeated("brand new message") is False

    async def test_empty_text_published(self, processor, bus):
        """An empty-text event is not a duplicate and should still be published."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_filtered", capture)

        await processor.handle_event(_processed_twitch_chat(text=""))

        assert len(published) == 1

    async def test_stt_event_published_as_stt_filtered(self, processor, bus):
        """stt_processed must map to stt_filtered, not twitch_chat_filtered."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("stt_filtered", capture)

        await processor.handle_event(_processed_stt())

        assert len(published) == 1
        assert published[0].type == "stt_filtered"

    async def test_filtered_event_preserves_user_and_text(self, processor, bus):
        """The *_filtered event must carry the same user and text as the input."""
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("twitch_chat_filtered", capture)

        await processor.handle_event(_processed_twitch_chat(text="hi there", user="alice"))

        assert published[0].user == "alice"
        assert published[0].text == "hi there"


# -----------------------------------------------------------------------
# AutonomousPromptProcessor
# -----------------------------------------------------------------------

class TestAutonomousPromptProcessor:
    """
    AutonomousPromptProcessor receives monologue_prompt events from the
    Cognitive layer and publishes ResponsePromptEvents for GenerationCoordinator.
    """

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def processor(self, bus):
        p = AutonomousPromptProcessor(max_age_seconds=30)
        p.register_subscriptions(bus)
        return p

    async def test_monologue_emits_response_prompt(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("response_prompt", capture)

        await processor.handle_event(_monologue_event())

        assert any(e.type == "response_prompt" for e in published)

    async def test_stale_monologue_dropped(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("response_prompt", capture)

        event = _monologue_event()
        event.timestamp = "2020-01-01T00:00:00+00:00"
        await processor.handle_event(event)

        assert not any(e.type == "response_prompt" for e in published)

    async def test_response_prompt_carries_prompt_text(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("response_prompt", capture)

        await processor.handle_event(_monologue_event(prompt="say something interesting"))

        assert published
        assert "say something interesting" in published[0].prompt

    async def test_fresh_monologue_not_filtered(self, processor, bus):
        published = []
        async def capture(e): published.append(e)
        bus.subscribe("response_prompt", capture)

        await processor.handle_event(_monologue_event())

        assert len(published) == 1
