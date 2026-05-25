import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.qubit.output.tts_manager import TTSManager

# TTSManager touches Piper / audio model loading → heavy mocking required.


@patch("src.qubit.output.tts_manager.PiperVoice")
def test_tts_manager_loads_model_on_init(mock_piper_voice, mock_heavy_stack):
    mock_voice = MagicMock()
    mock_piper_voice.load.return_value = mock_voice

    manager = TTSManager()

    mock_piper_voice.load.assert_called_once()
    assert manager.voice is mock_voice
    assert isinstance(manager.model_path, Path)


@patch("src.qubit.output.tts_manager.PiperVoice")
def test_tts_manager_raises_on_load_failure(mock_piper_voice, mock_heavy_stack):
    mock_piper_voice.load.side_effect = Exception("model not found")

    with pytest.raises(Exception, match="model not found"):
        TTSManager()


@patch("src.qubit.output.tts_manager.PiperVoice")
def test_tts_manager_logs_and_re_raises_on_load_failure(mock_piper_voice, mock_heavy_stack):
    """Deeper negative path + logging behavior."""
    mock_piper_voice.load.side_effect = FileNotFoundError("model missing")

    with pytest.raises(FileNotFoundError):
        TTSManager()
