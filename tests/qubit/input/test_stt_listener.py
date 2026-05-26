import pytest
from src.qubit.input.stt_listener import SpeechToTextListener


def test_stt_listener_instantiation():
    listener = SpeechToTextListener()
    assert listener is not None


@pytest.mark.asyncio
async def test_stt_listener_is_service_and_has_run_loop(mock_app):
    listener = SpeechToTextListener()
    assert hasattr(listener, "_run")
    # Safe to call start (it will wait for start signal and not actually open mic because of mocks)
    # We just verify it doesn't explode on construction + basic lifecycle
    await listener.start(mock_app)
    assert listener.app is mock_app
    await listener.stop()
