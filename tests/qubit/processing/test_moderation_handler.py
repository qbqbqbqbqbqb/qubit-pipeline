import sys
import pytest
from unittest.mock import MagicMock, AsyncMock

# Mock the heavy config module before importing ModerationHandler
sys.modules['config'] = MagicMock()
sys.modules['config.config'] = MagicMock()
sys.modules['config.config'].BLACKLISTED_WORDS_LIST = []
sys.modules['config.config'].WHITELISTED_WORDS_LIST = []

from src.qubit.processing.input_moderation_handler import ModerationHandler
from src.qubit.core.events import TwitchChatEvent, TwitchFollowEvent


@pytest.fixture
def moderation_handler():
    handler = ModerationHandler()
    handler.event_bus = AsyncMock()
    handler.logger = MagicMock()
    return handler


@pytest.mark.asyncio
async def test_moderation_handler_sanitises_chat(moderation_handler):
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
async def test_moderation_handler_publishes_processed_events(moderation_handler):
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
