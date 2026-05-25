import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from src.qubit.output.output_handler import OutputHandler
from src.qubit.core.events import ResponseGeneratedEvent

# Output layer tests (TTS, OBS, audio) are heavy — use shared mocking strategy.


@pytest.fixture
def output_handler(mock_tts_handler, mock_obs_handler, mock_vtube_handler, mock_memory_handler):
    handler = OutputHandler(
        tts_handler=mock_tts_handler,
        obs_handler=mock_obs_handler,
        vtube_studio_handler=mock_vtube_handler,
        memory_handler=mock_memory_handler,
        max_age_seconds=30,
        enable_subtitles=True,
    )
    handler.logger = MagicMock()
    return handler


@pytest.fixture
def output_handler_no_extras(mock_tts_handler, mock_obs_handler):
    """Minimal handler without vtube or memory."""
    handler = OutputHandler(
        tts_handler=mock_tts_handler,
        obs_handler=mock_obs_handler,
        max_age_seconds=30,
        enable_subtitles=False,
    )
    handler.logger = MagicMock()
    return handler


@pytest.mark.asyncio
async def test_handle_response_queues_valid_twitch_message(output_handler, sample_response_event, mock_memory_handler, mock_heavy_stack):
    event = sample_response_event
    event.source = "twitch_chat_processed"
    event.prompt = "How are you?"

    await output_handler.handle_response(event)

    assert len(output_handler.queue) == 1
    item = output_handler.queue[0]
    assert item["prompt"] == "How are you?"
    assert "Hello there" in item["response"]
    mock_memory_handler.handle_event.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_handle_response_queues_monologue_when_no_prompt(output_handler_no_extras, mock_memory_handler):
    event = ResponseGeneratedEvent(
        type="response_generated",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={},
        prompt=None,
        source="cognitive",
        response="Just thinking out loud here.",
    )

    await output_handler_no_extras.handle_response(event)

    assert len(output_handler_no_extras.queue) == 1
    item = output_handler_no_extras.queue[0]
    assert item["prompt"] is None
    assert item["source"] == "cognitive"


@pytest.mark.asyncio
async def test_handle_response_skips_empty_response(output_handler, mock_tts_handler):
    event = ResponseGeneratedEvent(
        type="response_generated",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={},
        prompt="Say something",
        source="twitch_chat_processed",
        response="   ",
    )

    await output_handler.handle_response(event)

    assert len(output_handler.queue) == 0
    mock_tts_handler.speak.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_response_skips_blacklisted_via_sanitiser(output_handler, mock_heavy_stack):
    # Inject a blacklist that will cause sanitiser to still return valid=True but we can test the path
    # (real filtering happens in filter_utils; here we just ensure it goes through)
    with patch.object(output_handler.dialogue_sanitiser, "is_valid", return_value=(False, "blocked")):
        event = ResponseGeneratedEvent(
            type="response_generated",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={},
            prompt="Bad",
            source="twitch",
            response="something offensive",
        )
        await output_handler.handle_response(event)

    assert len(output_handler.queue) == 0


@pytest.mark.asyncio
async def test_handle_text_output_with_all_handlers(output_handler, mock_tts_handler, mock_obs_handler, mock_vtube_handler):
    text = "Speaking now"

    await output_handler._handle_text_output(text)

    mock_obs_handler.update_subtitle_text_and_style.assert_awaited_once()
    mock_tts_handler.speak.assert_awaited_once_with(text)
    assert mock_vtube_handler.speaking is False  # reset in finally
    mock_vtube_handler.mouthanimation.assert_awaited()


@pytest.mark.asyncio
async def test_handle_text_output_without_vtube_or_subtitles(mock_tts_handler, mock_obs_handler):
    handler = OutputHandler(
        tts_handler=mock_tts_handler,
        obs_handler=mock_obs_handler,
        vtube_studio_handler=None,
        enable_subtitles=False,
    )
    handler.logger = MagicMock()

    await handler._handle_text_output("Just TTS")

    mock_tts_handler.speak.assert_awaited_once_with("Just TTS")
    mock_obs_handler.update_subtitle_text_and_style.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_timestamp_stale_drops_old_items(output_handler):
    old_item = {
        "prompt": "old",
        "response": "stuff",
        "source": "test",
        "timestamp": datetime.now(timezone.utc) - timedelta(seconds=60),
    }

    is_stale = await output_handler._check_if_timestamp_stale(old_item)
    assert is_stale is True


@pytest.mark.asyncio
async def test_check_timestamp_stale_keeps_fresh_items(output_handler):
    fresh_item = {
        "prompt": "fresh",
        "response": "stuff",
        "source": "test",
        "timestamp": datetime.now(timezone.utc),
    }

    is_stale = await output_handler._check_if_timestamp_stale(fresh_item)
    assert is_stale is False


@pytest.mark.asyncio
async def test_append_to_queue_distinguishes_twitch_vs_other(output_handler):
    twitch_event = ResponseGeneratedEvent(
        type="response_generated", timestamp=datetime.now(timezone.utc).isoformat(),
        data={}, prompt="hi", source="twitch_chat_processed", response="yo"
    )
    other_event = ResponseGeneratedEvent(
        type="response_generated", timestamp=datetime.now(timezone.utc).isoformat(),
        data={}, prompt=None, source="monologue", response="solo"
    )

    await output_handler._append_to_queue(twitch_event)
    await output_handler._append_to_queue(other_event)

    assert output_handler.queue[0]["prompt"] == "hi"
    assert output_handler.queue[1]["prompt"] is None
    assert output_handler.queue[1]["source"] == "monologue"
