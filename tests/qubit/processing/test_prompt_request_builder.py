import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.generation.prompt_builder import PromptRequestBuilder
from src.qubit.core.events import ResponsePromptEvent, Event, TwitchChatEvent


class TestPromptRequestBuilder:
    @pytest.fixture
    def dispatcher(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, dispatcher):
        return PromptRequestBuilder(dispatcher)

    def test_builders_mapping_exists(self, handler):
        assert "twitch_chat_processed" in handler.builders
        assert "monologue_prompt" in handler.builders

    @pytest.mark.asyncio
    async def test_handle_chat_event_returns_prompt_event(self, handler):
        event = TwitchChatEvent(
            type="twitch_chat_processed",
            timestamp="now",
            data={},
            user="test",
            text="hello"
        )
        result = await handler.handle_event(event)
        assert isinstance(result, ResponsePromptEvent)
        assert result.prompt == "test: hello"
        assert result.user == "test"

    @pytest.mark.asyncio
    async def test_handle_unknown_event_returns_none(self, handler):
        event = Event(type="unknown", timestamp="now", data={})
        result = await handler.handle_event(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_queue_event_calls_dispatcher(self, handler):
        event = MagicMock()
        handler.dispatcher.enqueue = AsyncMock()
        await handler.queue_event(event)
        handler.dispatcher.enqueue.assert_awaited_once_with(event)
