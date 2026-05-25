import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

pytest.importorskip("twitchAPI", reason="OutputHandler imports config which pulls twitchAPI")

from src.qubit.output.output_handler import OutputHandler
from src.qubit.core.events import ResponseGeneratedEvent


@pytest.fixture
def mock_tts():
    tts = MagicMock()
    tts.speak = AsyncMock()
    return tts


@pytest.fixture
def mock_obs():
    obs = MagicMock()
    obs.update_subtitle = AsyncMock()
    return obs


@pytest.fixture
def output_handler(mock_tts, mock_obs):
    with patch("src.qubit.output.output_handler.BLACKLISTED_WORDS_LIST", []), \
         patch("src.qubit.output.output_handler.WHITELISTED_WORDS_LIST", []):
        handler = OutputHandler(
            tts_handler=mock_tts,
            obs_handler=mock_obs,
            enable_subtitles=True,
            max_age_seconds=30
        )
        handler.logger = MagicMock()
        return handler


@pytest.mark.asyncio
async def test_handle_response_sanitises_and_queues(output_handler, mock_tts, mock_obs):
    event = ResponseGeneratedEvent(
        type="response_generated",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={},
        prompt="Say something",
        source="cognitive",
        response="Hello there! This is a test response."
    )

    await output_handler.handle_response(event)

    # Should have called TTS
    mock_tts.speak.assert_awaited_once()
    # Should have updated OBS if enabled
    mock_obs.update_subtitle.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_response_skips_invalid(output_handler, mock_tts):
    event = ResponseGeneratedEvent(
        type="response_generated",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={},
        prompt="Bad one",
        source="cognitive",
        response=""  # empty -> should skip
    )

    await output_handler.handle_response(event)

    mock_tts.speak.assert_not_awaited()
