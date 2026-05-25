import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json

from src.qubit.output.obs_handler import OBSHandler


def test_obs_handler_instantiation():
    settings = MagicMock(obs_password="pw", obs_host="localhost", obs_port=4455)
    handler = OBSHandler(settings)
    assert handler is not None
    assert handler.url == "ws://localhost:4455"


def test_build_auth_string_produces_string():
    settings = MagicMock(obs_password="secret")
    handler = OBSHandler(settings)
    auth = handler._build_auth_string("salt123", "challenge456")
    assert isinstance(auth, str)
    assert len(auth) > 0


@pytest.mark.asyncio
async def test_update_subtitle_text_and_style_success_path():
    settings = MagicMock(obs_password="pw", obs_host="127.0.0.1", obs_port=4455)
    handler = OBSHandler(settings)

    mock_ws = MagicMock()
    mock_ws.recv.side_effect = [
        json.dumps({"d": {"authentication": {"salt": "s", "challenge": "c"}}}),
        json.dumps({"d": {}}),
        json.dumps({"ok": True}),
    ]

    async def fake_to_thread(func, *args, **kwargs):
        # Simulate running the sync connect_to_obs
        return func(*args, **kwargs)

    with patch.object(handler, "connect_to_obs", return_value=mock_ws), \
         patch("asyncio.to_thread", side_effect=fake_to_thread):

        await handler.update_subtitle_text_and_style("TTS_Subtitles", "Hello OBS")

        assert mock_ws.send.called
        mock_ws.close.assert_called()


@pytest.mark.asyncio
async def test_update_subtitle_text_and_style_handles_errors_gracefully():
    settings = MagicMock()
    handler = OBSHandler(settings)

    async def fake_to_thread(func, *args, **kwargs):
        raise Exception("Connection failed")

    with patch("asyncio.to_thread", side_effect=fake_to_thread):
        # The method catches all exceptions internally
        await handler.update_subtitle_text_and_style("Test", "text")
