import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.qubit.core.server import WebSocketServerService


def test_websocket_server_service_instantiation():
    srv = WebSocketServerService(host="127.0.0.1", port=0)  # port 0 for test
    assert srv.host == "127.0.0.1"
    assert srv.port == 0
    assert srv.name == "websocket_server"
    assert isinstance(srv.connected_clients, set)


@pytest.mark.asyncio
async def test_start_creates_server_and_stop_closes_it():
    srv = WebSocketServerService(host="127.0.0.1", port=0)
    mock_app = type("App", (), {"event_bus": MagicMock(), "state": MagicMock()})()

    # Patch the actual websockets.serve so we don't open real sockets in unit test
    with patch("src.qubit.core.server.websockets.serve", new_callable=AsyncMock) as mock_serve:
        fake_server = AsyncMock()
        fake_server.close = AsyncMock()
        fake_server.wait_closed = AsyncMock()
        mock_serve.return_value = fake_server

        await srv.start(mock_app)
        assert srv.server is fake_server

        await srv.stop()
        fake_server.close.assert_called_once()
        fake_server.wait_closed.assert_awaited_once()
