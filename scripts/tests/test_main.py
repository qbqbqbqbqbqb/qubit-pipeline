import asyncio
import sys
import signal
import pytest
from unittest import mock

import scripts.main as main  

@pytest.mark.asyncio
async def test_token_refresher_loop_runs_once(monkeypatch):
    called = False
    async def fake_refresh():
        nonlocal called
        called = True

    monkeypatch.setattr(main, "refresh_twitch_token", fake_refresh)

    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await main.token_refresher_loop()

    assert called is True

@pytest.mark.asyncio
async def test_keep_alive_loop_runs_and_exits(monkeypatch):
    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await main.keep_alive_loop()

@pytest.mark.asyncio
async def test_main_success(monkeypatch):
    mock_client = mock.AsyncMock()
    mock_client.start.return_value = True
    mock_client.disconnect.return_value = asyncio.Future()
    mock_client.disconnect.return_value.set_result(None)

    monkeypatch.setattr(main, "TwitchClient", lambda: mock_client)
    monkeypatch.setattr(main, "refresh_twitch_token", mock.AsyncMock())

    original_gather = asyncio.gather

    async def fake_gather(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "gather", fake_gather)

    with pytest.raises(asyncio.CancelledError):
        await main.main()

    mock_client.start.assert_called_once()
    mock_client.disconnect.assert_called_once()
    main.refresh_twitch_token.assert_called_once()

def test_handle_exit_calls_disconnect_and_exits(monkeypatch):
    mock_client = mock.AsyncMock()
    mock_client.disconnect.return_value = asyncio.Future()
    mock_client.disconnect.return_value.set_result(None)

    main.twitch_client = mock_client

    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    with pytest.raises(SystemExit):
        main.handle_exit(signal.SIGINT, None)

    mock_client.disconnect.assert_called_once()
