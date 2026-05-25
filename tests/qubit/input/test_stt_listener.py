import pytest
from src.qubit.input.stt_listener import SpeechToTextListener


def test_stt_listener_instantiation():
    listener = SpeechToTextListener()
    assert listener is not None


@pytest.mark.asyncio
async def test_stt_listener_listen_does_not_crash():
    listener = SpeechToTextListener()
    # Currently a no-op stub
    await listener.listen(None)
