import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np

from src.qubit.output.tts_handler import TTSHandler


@pytest.fixture
def tts_handler_with_mock_manager(mock_tts_manager):
    return TTSHandler(tts_manager=mock_tts_manager)


@pytest.mark.asyncio
async def test_speak_skips_empty_text(tts_handler_with_mock_manager):
    await tts_handler_with_mock_manager.speak("   ")
    # Should not attempt any synthesis
    tts_handler_with_mock_manager.tts_manager.voice.synthesize_wav.assert_not_called()


@pytest.mark.asyncio
async def test_speak_calls_synthesis_and_playback(tts_handler_with_mock_manager):
    # Prepare fake wav bytes
    fake_wav = b"RIFF....WAVEfmt "  # minimal fake header is enough for our mocks

    with patch.object(tts_handler_with_mock_manager, "_generate_wav_bytes", return_value=fake_wav), \
         patch.object(tts_handler_with_mock_manager, "_decode_wav_bytes", return_value=(24000, np.array([0, 1, 2], dtype=np.int16))), \
         patch.object(tts_handler_with_mock_manager, "_play_audio") as mock_play:

        await tts_handler_with_mock_manager.speak("Hello world")

        mock_play.assert_called_once()


def test_generate_wav_bytes_uses_tts_manager(tts_handler_with_mock_manager):
    tts_handler_with_mock_manager.tts_manager.voice.synthesize_wav.reset_mock()

    with patch.object(tts_handler_with_mock_manager, "_get_speaker_id", return_value=0), \
         patch("wave.open") as mock_wave_open:
        mock_wav_file = MagicMock()
        mock_wave_open.return_value.__enter__.return_value = mock_wav_file

        wav = tts_handler_with_mock_manager._generate_wav_bytes("test phrase")

    tts_handler_with_mock_manager.tts_manager.voice.synthesize_wav.assert_called_once()
    assert isinstance(wav, bytes)


def test_decode_wav_bytes_roundtrip():
    handler = TTSHandler(tts_manager=MagicMock())
    # Create a tiny valid wav in memory
    import io, wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00\x01\x00\x00\x00")
    wav_bytes = buf.getvalue()

    sr, audio = handler._decode_wav_bytes(wav_bytes)
    assert sr == 16000
    assert isinstance(audio, np.ndarray)


@patch("src.qubit.output.tts_handler.pyaudio")
def test_play_audio_opens_stream_and_writes(mock_pyaudio_module):
    handler = TTSHandler(tts_manager=MagicMock())

    mock_stream = MagicMock()
    mock_pa_instance = MagicMock()
    mock_pa_instance.open.return_value = mock_stream
    mock_pyaudio_module.PyAudio.return_value = mock_pa_instance

    audio = np.array([100, 200], dtype=np.int16)
    handler._play_audio(22050, audio)

    mock_pa_instance.open.assert_called_once()
    mock_stream.write.assert_called_once()
    mock_stream.stop_stream.assert_called_once()
    mock_pa_instance.terminate.assert_called_once()
