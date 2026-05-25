import sys
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

# === Pre-emptive heavy mocking for all /output tests ===
# Must run before any output module or config is imported by test files.

HEAVY_MODULES = [
    "twitchAPI",
    "twitchAPI.type",
    "piper",
    "pyaudio",
    "websocket",
    "inflect",
]

for mod_name in HEAVY_MODULES:
    sys.modules[mod_name] = MagicMock()

# Fully mock config so no real file I/O or twitch imports happen
mock_config = MagicMock()
mock_config.BLACKLISTED_WORDS_LIST = []
mock_config.WHITELISTED_WORDS_LIST = []
mock_config.TTS_SPEAKER_NAME = "p236"
mock_config.TTS_MODEL_NAME = "en_GB-vctk-medium.onnx"
mock_config.TTS_SUBTITLE_NAME = "TTS_Subtitles"
mock_config.BOT_NAME = "Qubit"
mock_config.ROOT = Path("/fake/project/root")
mock_config.ACRONYMS_LIST = []

sys.modules["config"] = MagicMock()
sys.modules["config.config"] = mock_config


# === Reusable fixtures for output tests ===

def _make_mock_tts_manager():
    m = MagicMock()
    m.model_path = Path("/fake/model.onnx")
    m.voice = MagicMock()
    m.voice.synthesize_wav = MagicMock()
    return m


import pytest

@pytest.fixture
def mock_tts_manager():
    return _make_mock_tts_manager()


@pytest.fixture
def mock_tts_handler():
    tts = MagicMock()
    tts.speak = AsyncMock()
    return tts


@pytest.fixture
def mock_obs_handler():
    obs = MagicMock()
    obs.update_subtitle_text_and_style = AsyncMock()
    return obs


@pytest.fixture
def mock_vtube_handler():
    v = MagicMock()
    v.speaking = False
    v.mouthanimation = AsyncMock()
    return v


@pytest.fixture
def mock_memory_writer():
    m = MagicMock()
    m.handle_event = AsyncMock()
    return m


@pytest.fixture
def sample_response_event():
    from datetime import datetime, timezone
    from src.qubit.core.events import ResponseGeneratedEvent

    return ResponseGeneratedEvent(
        type="response_generated",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={},
        prompt="Test prompt",
        source="twitch_chat_processed",
        response="Hello there, this is a clean response!",
    )
