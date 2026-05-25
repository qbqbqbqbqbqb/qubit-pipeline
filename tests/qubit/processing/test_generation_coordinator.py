import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Mock torch and transformers before any imports that might trigger them
sys.modules['torch'] = MagicMock()
sys.modules['transformers'] = MagicMock()
sys.modules['peft'] = MagicMock()

from src.qubit.generation.generation_coordinator import GenerationCoordinator
from src.qubit.core.events import ResponsePromptEvent, ResponseGeneratedEvent


class TestGenerationCoordinator:
    @pytest.fixture
    def coordinator(self):
        # Mock the new LLMService
        mock_service = MagicMock()
        mock_service.generate_with_retries = AsyncMock(return_value="Generated response")
        return GenerationCoordinator(llm_service=mock_service)

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self, coordinator):
        event = MagicMock(spec=ResponsePromptEvent)
        event.type = "response_prompt"
        event.data = {"user": "test"}
        event.prompt = "Test prompt"

        await coordinator.enqueue(event)

        assert coordinator.queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_is_stale_logic(self, coordinator):
        from datetime import datetime, timedelta, timezone
        old_event = MagicMock(spec=ResponsePromptEvent)
        old_event.timestamp = (datetime.now(timezone.utc) - timedelta(seconds=40)).isoformat()
        coordinator.max_age = timedelta(seconds=30)

        assert coordinator._is_stale(old_event) is True

        recent_event = MagicMock(spec=ResponsePromptEvent)
        recent_event.timestamp = datetime.now(timezone.utc).isoformat()
        assert coordinator._is_stale(recent_event) is False

    @pytest.mark.asyncio
    async def test_generate_response_calls_assembler_and_llm(self, coordinator):
        coordinator.event_bus = AsyncMock()

        mock_assembler = MagicMock()
        mock_assembler.build.return_value = "Final prompt"

        with patch("src.qubit.generation.generation_coordinator.PromptAssembler") as MockAssembler, \
             patch("src.qubit.generation.generation_coordinator.core_system_module") as mock_core, \
             patch("src.qubit.generation.generation_coordinator.personality_module") as mock_personality, \
             patch("src.qubit.generation.generation_coordinator.stream_type_module") as mock_stream, \
             patch("src.qubit.generation.generation_coordinator.input_module") as mock_input:

            MockAssembler.return_value = mock_assembler
            mock_core.return_value = MagicMock()
            mock_personality.return_value = MagicMock()
            mock_stream.return_value = MagicMock()
            mock_input.return_value = MagicMock()

            coordinator.llm_service.generate_with_retries = AsyncMock(return_value="LLM response")

            event = MagicMock(spec=ResponsePromptEvent)
            event.data = {"user": "test"}
            event.prompt = "Test prompt"

            response = await coordinator._generate_response(event)

            assert response == "LLM response"
            coordinator.llm_service.generate_with_retries.assert_awaited()


    @pytest.mark.asyncio
    async def test_publish_response_creates_and_publishes_event(self, coordinator):
        mock_event_bus = AsyncMock()
        coordinator.event_bus = mock_event_bus

        event = MagicMock(spec=ResponsePromptEvent)
        event.data = {"user": "test"}
        event.prompt = "Test prompt"
        event.source = "test_source"

        response = "Generated response"

        await coordinator._publish_response(event, response)

        mock_event_bus.publish.assert_awaited_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert published_event.type == "response_generated"
        assert published_event.response == "Generated response"
        assert published_event.prompt == "Test prompt"
