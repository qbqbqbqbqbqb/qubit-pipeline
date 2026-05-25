import pytest
from unittest.mock import MagicMock, AsyncMock

# This test benefits from the shared heavy mocking infrastructure.
# The config mocking that was previously done here is now largely covered
# by the broader strategy in conftest.py and AGENTS.md.

from src.qubit.processing.input_moderation_handler import ModerationHandler
from src.qubit.core.events import TwitchChatEvent, TwitchFollowEvent


@pytest.fixture
def moderation_handler():
    handler = ModerationHandler()
    handler.event_bus = AsyncMock()
    handler.logger = MagicMock()
    return handler


@pytest.mark.asyncio
async def test_moderation_handler_sanitises_chat(moderation_handler, mock_heavy_stack):
    event = TwitchChatEvent(
        type="twitch_chat",
        timestamp="now",
        data={},
        user="baduser",
        text="some message"
    )

    await moderation_handler.handle_event(event)

    moderation_handler.event_bus.publish.assert_awaited_once()
    published = moderation_handler.event_bus.publish.call_args[0][0]
    assert published.type == "twitch_chat_processed"


@pytest.mark.asyncio
async def test_moderation_handler_publishes_processed_events(moderation_handler, mock_heavy_stack):
    follow_event = TwitchFollowEvent(
        type="twitch_follow",
        timestamp="now",
        data={},
        user="newfollower",
        followed_at="now"
    )

    await moderation_handler.handle_event(follow_event)

    moderation_handler.event_bus.publish.assert_awaited_once()
    published = moderation_handler.event_bus.publish.call_args[0][0]
    assert published.type == "twitch_follow_processed"


@pytest.mark.asyncio
async def test_moderation_handler_fuzz_style_various_events(moderation_handler, mock_heavy_stack):
    """Fuzz-style: throw many different event shapes at the moderation handler."""
    import random
    from src.qubit.core.events import Event

    candidates = [
        Event(type="twitch_chat", timestamp="now", data={"text": "normal"}),
        Event(type="twitch_chat", timestamp="now", data={"text": "badword offensive"}),
        Event(type="twitch_follow", timestamp="now", data={"user": "someone"}),
        Event(type="unknown_type", timestamp="now", data={}),
        Event(type="twitch_chat", timestamp="now", data={}),  # missing text
    ]

    for _ in range(20):
        ev = random.choice(candidates)
        # Should never raise
        await moderation_handler.handle_event(ev)
