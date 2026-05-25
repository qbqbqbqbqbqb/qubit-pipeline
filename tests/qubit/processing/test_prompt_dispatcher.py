import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Skip if torch is not available (since prompt_dispatcher uses AsyncHuggingFaceLLM which requires torch)
pytest.importorskip("torch", reason="PromptDispatcher requires torch and transformers")

from src.qubit.processing.prompt_dispatcher import PromptDispatcher
from src.qubit.core.events import ResponsePromptEvent, ResponseGeneratedEvent
from src.qubit.models.async_hf_model_manager import AsyncHuggingFaceLLM


class TestPromptDispatcher:
    @pytest.fixture
    def dispatcher(self):
        # Mock the LLM client
        mock_llm = MagicMock()
        mock_llm.generate_response = AsyncMock(return_value="Generated response")
        return PromptDispatcher(llm_client=mock_llm)

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self, dispatcher):
        event = MagicMock(spec=ResponsePromptEvent)
        event.type = "response_prompt"
        event.data = {"user": "test"}
        event.prompt = "Test prompt"

        await dispatcher.enqueue(event)

        assert dispatcher.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_is_stale_logic(self, dispatcher):
        from datetime import datetime, timedelta, timezone
        old_event = MagicMock(spec=ResponsePromptEvent)
        old_event.timestamp = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
        dispatcher.max_age = timedelta(seconds=30)

        assert dispatcher._is_stale(old_event) is True

        recent_event = MagicMock(spec=ResponsePromptEvent)
        recent_event.timestamp = datetime.now(timezone.utc).isoformat()
        assert dispatcher._is_stale(recent_event) is False

    @pytest.mark.asyncio
    async def test_generate_response_calls_assembler_and_llm(self, dispatcher):
        # Mock the assembler and the LLM
        mock_assembler = MagicMock()
        mock_assembler.build = MagicMock(return_value="Final prompt")
        dispatcher.llm.generate_response = AsyncMock(return_value="LLM response")

        event = MagicMock(spec=ResponsePromptEvent)
        event.data = {"user": "test"}
        event.prompt = "Test prompt"

        # We need to mock the PromptAssembler and the modules it uses
        with patch("src.qubit.processing.prompt_dispatcher.PromptAssembler") as MockAssembler, \
             patch("src.qubit.processing.prompt_dispatcher.core_system_module") as mock_core, \
             patch("src.qubit.processing.prompt_dispatcher.personality_module") as mock_personality, \
             patch("src.qubit.processing.prompt_dispatcher.stream_type_module") as mock_stream, \
             patch("src.qubit.processing.prompt_dispatcher.input_module") as mock_input:

            MockAssembler.return_value = mock_assembler
            mock_core.return_value = MagicMock()
            mock_personality.return_value = MagicMock()
            mock_stream.return_value = MagicMock()
            mock_input.return_value = MagicMock()

            response = await dispatcher._generate_response(event)

            assert response == "LLM response"
            dispatcher.llm.generate_response.assert_awaited_once_with("Final prompt")

    @pytest.mark.asyncio
    async def test_publish_response_creates_and_publishes_event(self, dispatcher):
        mock_event_bus = AsyncMock()
        dispatcher.event_bus = mock_event_bus

        event = MagicMock(spec=ResponsePromptEvent)
        event.data = {"user": "test"}
        event.prompt = "Test prompt"

        response = "Generated response"

        await dispatcher._publish_response(event, response)

        mock_event_bus.publish.assert_awaited_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.type == "response_generated"
        assert published_event.response == "Generated response"
        assert published_event.prompt == "Test prompt"
