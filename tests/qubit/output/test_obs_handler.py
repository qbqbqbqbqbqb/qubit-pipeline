import pytest
from unittest.mock import MagicMock, AsyncMock

pytest.importorskip("websocket", reason="OBSHandler requires websocket-client which may pull heavy deps")

from src.qubit.output.obs_handler import OBSHandler


def test_obs_handler_instantiation():
    settings = MagicMock()
    handler = OBSHandler(settings)
    assert handler is not None
    assert hasattr(handler, "update_subtitle")


@pytest.mark.asyncio
async def test_update_subtitle_does_not_crash_without_connection():
    settings = MagicMock()
    handler = OBSHandler(settings)
    # Should handle gracefully if not connected
    await handler.update_subtitle("Test subtitle")
