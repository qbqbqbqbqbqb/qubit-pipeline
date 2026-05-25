import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# twitchAPI pre-mocked in conftest for collection.

from unittest.mock import MagicMock, AsyncMock, patch
from src.qubit.input.twitch.listener import TwitchListener
from src.qubit.core.service import Service


class TestTwitchListener:
    def test_twitch_listener_instantiation(self):
        settings = MagicMock()
        settings.twitch_channel = "testchannel"
        listener = TwitchListener(settings=settings)
        assert listener.name == "twitch"
        assert listener.settings is settings
        assert listener.connected is False

    @pytest.mark.asyncio
    async def test_start_calls_super(self):
        settings = MagicMock()
        listener = TwitchListener(settings)
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.event_bus = MagicMock()

        with patch.object(Service, "start", new_callable=AsyncMock) as mock_super_start:
            await listener.start(mock_app)
            mock_super_start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_disconnects_resources(self):
        settings = MagicMock()
        listener = TwitchListener(settings)

        listener.chat = MagicMock()
        listener.twitch_bot = AsyncMock()
        listener.twitch_streamer = AsyncMock()
        listener.eventsub = AsyncMock()
        listener.connected = True

        await listener.stop()

        listener.chat.stop.assert_called_once()
        listener.twitch_bot.close.assert_awaited_once()
        listener.twitch_streamer.close.assert_awaited_once()
        assert listener.connected is False
