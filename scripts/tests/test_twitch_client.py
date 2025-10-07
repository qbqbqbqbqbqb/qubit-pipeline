import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from scripts.twitch_client import TwitchClient
from twitchAPI.type import AuthScope, ChatEvent
from unittest.mock import AsyncMock, patch

@pytest.fixture
def fake_settings():
    class Settings:
        twitch_client_id = "client_id"
        twitch_client_secret = "client_secret"
        bot_oauth_token = "bot_token"
        bot_refresh_token = "bot_refresh"
        streamer_oauth_token = "streamer_token"
        streamer_refresh_token = "streamer_refresh"
        twitch_channel = "test_channel"
    return Settings()

@pytest.fixture
def fake_logger():
    return Mock()

@pytest.mark.asyncio
@patch("scripts.twitch_client.Twitch", autospec=True)
@patch("scripts.twitch_client.Chat", autospec=True)
async def test_start_success(mock_chat_class, mock_twitch_class, fake_settings, fake_logger):
    client = TwitchClient(fake_settings, fake_logger)

    mock_twitch_instance = AsyncMock()
    mock_twitch_class.return_value = mock_twitch_instance

    mock_chat_instance = AsyncMock()
    mock_chat_class.return_value = mock_chat_instance
    mock_chat_instance.start = Mock()

    client._authenticate_bot_account = AsyncMock()
    client._authenticate_streamer_account = AsyncMock()
    client._setup_chat = AsyncMock()

    result = await client.start()

    assert result is True
    assert client.accounts_connected is True

    fake_logger.info.assert_any_call("[start] Starting TwitchClient...")
    fake_logger.info.assert_any_call(f"[start] Connected to Twitch channel: {fake_settings.twitch_channel}")

@pytest.mark.asyncio
@patch("scripts.twitch_client.Twitch", autospec=True)
async def test_authenticate_bot_account(mock_twitch_class, fake_settings, fake_logger):
    client = TwitchClient(fake_settings, fake_logger)

    mock_twitch_instance = AsyncMock()
    mock_twitch_class.return_value = mock_twitch_instance

    await client._authenticate_bot_account()

    mock_twitch_class.assert_called_once_with(fake_settings.twitch_client_id, fake_settings.twitch_client_secret)
    mock_twitch_instance.set_user_authentication.assert_awaited_once_with(
        fake_settings.bot_oauth_token,
        client.bot_scopes,
        fake_settings.bot_refresh_token,
    )
    fake_logger.info.assert_any_call("[_authenticate_bot_account] Authenticating bot account...")

@pytest.mark.asyncio
@patch("scripts.twitch_client.Twitch", autospec=True)
async def test_authenticate_streamer_account_with_tokens(mock_twitch_class, fake_settings, fake_logger):
    client = TwitchClient(fake_settings, fake_logger)

    mock_twitch_instance = AsyncMock()
    mock_twitch_class.return_value = mock_twitch_instance

    await client._authenticate_streamer_account()

    mock_twitch_class.assert_called_once_with(fake_settings.twitch_client_id, fake_settings.twitch_client_secret)
    mock_twitch_instance.set_user_authentication.assert_awaited_once_with(
        fake_settings.streamer_oauth_token,
        client.streamer_scopes,
        fake_settings.streamer_refresh_token,
    )
    fake_logger.info.assert_any_call("[_authenticate_streamer_account] Authenticating streamer account...")

@pytest.mark.asyncio
@patch("scripts.twitch_client.Chat", new_callable=AsyncMock)
async def test_setup_chat(mock_chat_class, fake_settings, fake_logger):
    mock_chat_instance = Mock()
    mock_chat_instance.register_event = Mock()
    mock_chat_instance.start = Mock()

    mock_chat_class.return_value = mock_chat_instance

    client = TwitchClient(fake_settings, fake_logger)
    client.twitch_bot = Mock()

    client._on_ready = Mock()
    client._on_message = Mock()
    client._on_subscription = Mock()
    client._on_raid = Mock()

    await client._setup_chat()

    mock_chat_instance.register_event.assert_any_call(ChatEvent.READY, client._on_ready)
    mock_chat_instance.start.assert_called_once()

@pytest.mark.asyncio
async def test_on_ready_success(fake_settings, fake_logger):
    client = TwitchClient(fake_settings, fake_logger)

    event = Mock()
    event.chat.join_room = AsyncMock()

    await client._on_ready(event)

    event.chat.join_room.assert_awaited_once_with(fake_settings.twitch_channel)
    fake_logger.info.assert_any_call("[_on_ready] Bot ready, joining channel...")
    fake_logger.info.assert_any_call(f"[_on_ready] Joined channel: {fake_settings.twitch_channel}")

@pytest.mark.asyncio
async def test_on_message_logs(fake_logger):
    client = TwitchClient(Mock(), fake_logger)
    msg = Mock()
    msg.user.name = "testuser"
    msg.text = "hello world"

    await client._on_message(msg)

    fake_logger.debug.assert_called_with(f"[_on_message] Message from testuser: hello world")

@pytest.mark.asyncio
async def test_on_message_empty_text_does_not_log(fake_logger):
    client = TwitchClient(Mock(), fake_logger)
    msg = Mock()
    msg.user.name = "testuser"
    msg.text = "   "

    await client._on_message(msg)

    fake_logger.debug.assert_not_called()

@pytest.mark.asyncio
async def test_on_subscription_logs(fake_logger):
    client = TwitchClient(Mock(), fake_logger)
    sub = Mock()
    sub.room.name = "channel"
    sub.sub_plan = "prime"

    await client._on_subscription(sub)

    fake_logger.info.assert_called_with("[_on_subscription] New subscription in channel: prime")

@pytest.mark.asyncio
async def test_on_raid_logs(fake_logger):
    client = TwitchClient(Mock(), fake_logger)
    raid_event = Mock()
    raid_event.from_broadcaster_user_name = "raider123"
    raid_event.viewers = 42

    await client._on_raid(raid_event)

    fake_logger.info.assert_called_with("[_on_raid] Raid from raider123 with 42 viewers")

@pytest.mark.asyncio
async def test_disconnect_stops_and_closes(fake_logger):
    client = TwitchClient(Mock(), fake_logger)

    mock_chat = Mock()
    client.chat = mock_chat

    client.twitch_bot = AsyncMock()
    client.twitch_streamer = AsyncMock()

    client.accounts_connected = True

    await client.disconnect()

    mock_chat.stop.assert_called_once()
    client.twitch_bot.close.assert_awaited_once()
    client.twitch_streamer.close.assert_awaited_once()
    assert client.accounts_connected is False

import pytest
from unittest.mock import AsyncMock, Mock
from scripts.twitch_client import TwitchClient
from twitchAPI.chat import ChatMessage

@pytest.mark.asyncio
async def test_on_message_responds_to_bits():
    # Arrange
    fake_settings = Mock()
    fake_logger = Mock()
    client = TwitchClient(fake_settings, fake_logger)

    client.chat = Mock()
    client.chat.send_message = AsyncMock()

    msg = Mock(spec=ChatMessage)
    msg.user = Mock()
    msg.user.name = "testuser"
    msg.text = "cheering with bits!"
    msg.tags = {'bits': '250'}

    await client._on_message(msg)

    client.chat.send_message.assert_awaited_once_with(
        "Thanks testuser for cheering 250 bits! 🎉"
    )

