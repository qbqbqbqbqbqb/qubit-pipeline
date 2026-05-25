import pytest

from src.qubit.output.vtube_studio_handler import VtubeStudioHandler


def test_vtube_studio_handler_is_instantiable():
    handler = VtubeStudioHandler()
    assert handler is not None


@pytest.mark.asyncio
async def test_vtube_send_does_nothing():
    handler = VtubeStudioHandler()
    # Currently a no-op stub — just ensure it can be called
    await handler.send("any text")
