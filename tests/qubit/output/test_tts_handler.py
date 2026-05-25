import pytest
from unittest.mock import MagicMock, AsyncMock, patch

pytest.importorskip("piper", reason="TTSHandler requires piper-tts + pyaudio + numpy")

from src.qubit.output.tts_handler import TTSHandler


def test_tts_handler_instantiation():
    handler = TTSHandler()
    assert handler is not None
    assert hasattr(handler, "speak")


@pytest.mark.asyncio
async def test_speak_handles_empty_text():
    handler = TTSHandler()
    # Should not raise
    await handler.speak("")
