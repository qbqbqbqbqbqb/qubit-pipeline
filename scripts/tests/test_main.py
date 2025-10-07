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

    monkeypatch.setattr("scripts.main.refresh_twitch_token", fake_refresh)

    async def fake_sleep(seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

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

    monkeypatch.setattr(main, "TwitchClient", lambda settings, logger: mock_client)
    monkeypatch.setattr(main, "refresh_twitch_token", mock.AsyncMock())

    async def trigger_shutdown():
        await asyncio.sleep(0.1)
        main.handle_signal(signal.SIGINT, None)

    await asyncio.gather(
        main.main(),
        trigger_shutdown(),
    )

    mock_client.start.assert_called_once()
    mock_client.disconnect.assert_called_once()

def test_handle_signal_sets_stop_event():
    main.stop_event.clear()
    main.handle_signal(signal.SIGINT, None)
    assert main.stop_event.is_set()

