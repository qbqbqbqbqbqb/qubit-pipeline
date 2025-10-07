import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from twitchAPI.oauth import AuthScope
from scripts.twitch_client import TwitchClient

class AsyncIterator:
    def __init__(self, items):
        self.items = items
    def __aiter__(self):
        self._iter = iter(self.items)
        return self
    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

@pytest.mark.asyncio
@patch('scripts.twitch_client.load_dotenv')
@patch('scripts.twitch_client.os.getenv')
async def test_init(mock_getenv, mock_load):
    mock_getenv.side_effect = lambda key, default=None: {
        'TWITCH_CLIENT_ID': 'test_app_id',
        'TWITCH_CLIENT_SECRET': 'test_secret',
        'BOT_OAUTH_TOKEN': 'bot_token',
        'BOT_REFRESH_TOKEN': 'bot_refresh',
        'STREAMER_OAUTH_TOKEN': 'streamer_token',
        'STREAMER_REFRESH_TOKEN': 'streamer_refresh',
        'TWITCH_CHANNEL': 'test_channel',
        'TWITCH_REDIRECT_URI': 'http://localhost'
    }.get(key, default)

    client = TwitchClient()

    assert client.app_id == 'test_app_id'
    assert client.app_secret == 'test_secret'
    assert client.bot_oauth_token == 'bot_token'
    assert client.bot_refresh_token == 'bot_refresh'
    assert client.streamer_oauth_token == 'streamer_token'
    assert client.streamer_refresh_token == 'streamer_refresh'
    assert client.channel_name == 'test_channel'
    assert client.redirect_uri == 'http://localhost'
    assert client.twitch_integration_enabled is False
    assert client.accounts_connected is False
    assert client.bot_scopes == [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT]
    assert client.streamer_scopes == [
        AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
        AuthScope.CHANNEL_MANAGE_RAIDS
    ]

@pytest.mark.asyncio
@patch.object(TwitchClient, 'connect', new_callable=AsyncMock)
async def test_start(mock_connect):
    client = TwitchClient()
    await client.start()
    assert client.twitch_integration_enabled is True
    mock_connect.assert_called_once()

@pytest.mark.asyncio
@patch.object(TwitchClient, '_authenticate_bot_account', new_callable=AsyncMock)
@patch.object(TwitchClient, '_authenticate_streamer_account', new_callable=AsyncMock)
@patch.object(TwitchClient, '_setup_chat', new_callable=AsyncMock)
async def test_connect_success(mock_setup, mock_auth_streamer, mock_auth_bot):
    client = TwitchClient()
    client.channel_name = 'test_channel'
    client.twitch_streamer = None

    result = await client.connect()

    assert result is True
    assert client.accounts_connected is True
    mock_auth_bot.assert_called_once()
    mock_auth_streamer.assert_called_once()
    mock_setup.assert_called_once()

@pytest.mark.asyncio
@patch.object(TwitchClient, '_authenticate_bot_account', side_effect=Exception('auth failed'))
async def test_connect_failure(mock_auth_bot):
    client = TwitchClient()
    result = await client.connect()
    assert result is False
    assert client.accounts_connected is False

@pytest.mark.asyncio
@patch('scripts.twitch_client.Twitch')
@patch('scripts.twitch_client.UserAuthenticator')
async def test_authenticate_bot_without_tokens(mock_user_authenticator_class, mock_twitch_class):
    client = TwitchClient()
    client.app_id = 'id'
    client.app_secret = 'secret'
    client.bot_oauth_token = None
    client.bot_refresh_token = None
    client.bot_scopes = [Mock()]
    client.redirect_uri = 'uri'

    mock_twitch_instance = AsyncMock()
    mock_twitch_class.return_value = mock_twitch_instance
    async def set_user_authentication(token, scopes, refresh):
        client.bot_oauth_token = token
        client.bot_refresh_token = refresh
    mock_twitch_instance.set_user_authentication = AsyncMock(side_effect=set_user_authentication)

    mock_auth_instance = Mock()
    mock_auth_instance.authenticate = AsyncMock(return_value=('new_token', 'new_refresh'))
    mock_user_authenticator_class.return_value = mock_auth_instance

    await client._authenticate_bot_account()

    mock_user_authenticator_class.assert_called_once_with(mock_twitch_instance, client.bot_scopes, url='uri')
    mock_auth_instance.authenticate.assert_awaited_once()
    mock_twitch_instance.set_user_authentication.assert_awaited_once_with('new_token', client.bot_scopes, 'new_refresh')
    assert client.bot_oauth_token == 'new_token'
    assert client.bot_refresh_token == 'new_refresh'

@pytest.mark.asyncio
@patch('scripts.twitch_client.Twitch')
async def test_authenticate_streamer_with_tokens(mock_twitch_class):
    client = TwitchClient()
    client.app_id = 'id'
    client.app_secret = 'secret'
    client.streamer_oauth_token = 'token'
    client.streamer_refresh_token = 'refresh'
    client.streamer_scopes = [Mock()]

    mock_twitch_instance = AsyncMock()
    mock_twitch_instance.set_user_authentication = AsyncMock()
    mock_twitch_instance.get_users = MagicMock(return_value=AsyncIterator([Mock()]))

    mock_twitch_class.return_value = mock_twitch_instance

    await client._authenticate_streamer_account()

    assert client.twitch_streamer is not None

@pytest.mark.asyncio
@patch('scripts.twitch_client.Chat')
@patch.object(TwitchClient, '_register_event_handlers', new_callable=AsyncMock)
async def test_setup_chat(mock_register, mock_chat):
    client = TwitchClient()
    client.twitch_bot = Mock()

    mock_chat_instance = AsyncMock()
    mock_chat.return_value = mock_chat_instance
    mock_chat_instance.start = Mock()

    await client._setup_chat()

    mock_chat.assert_called_once_with(client.twitch_bot)
    mock_register.assert_called_once_with(mock_chat_instance)

@pytest.mark.asyncio
@patch('scripts.twitch_client.logger')
async def test_on_ready(mock_logger):
    client = TwitchClient()
    event = Mock()
    event.chat.join_room = AsyncMock()
    client.channel_name = 'test_channel'

    await client._on_ready(event)

    event.chat.join_room.assert_awaited_once_with('test_channel')
    mock_logger.info.assert_called()

@pytest.mark.asyncio
@patch('scripts.twitch_client.logger')
async def test_on_message(mock_logger):
    client = TwitchClient()
    msg = Mock()
    msg.user.name = 'user'
    msg.text = 'hello'

    await client._on_message(msg)

    mock_logger.debug.assert_called_with('[TwitchClient] Message from user: hello')

@pytest.mark.asyncio
@patch('scripts.twitch_client.logger')
async def test_on_subscription(mock_logger):
    client = TwitchClient()
    sub = Mock()
    sub.room.name = 'room'
    sub.sub_plan = 'plan'

    await client._on_subscription(sub)

    mock_logger.info.assert_called_with('[TwitchClient] New subscription in room: plan')

@pytest.mark.asyncio
@patch('scripts.twitch_client.logger')
async def test_on_raid(mock_logger):
    client = TwitchClient()
    raid_event = Mock()
    raid_event.from_broadcaster_user_name = 'raider'
    raid_event.viewers = 100

    await client._on_raid(raid_event)

    mock_logger.info.assert_called_with('[TwitchClient] Raid from raider with 100 viewers')

@pytest.mark.asyncio
@patch('scripts.twitch_client.logger')
async def test_disconnect(mock_logger):
    client = TwitchClient()
    client.twitch_bot = AsyncMock()
    client.twitch_streamer = AsyncMock()
    client.accounts_connected = True
    client.twitch_integration_enabled = True

    await client.disconnect()

    client.twitch_bot.close.assert_awaited_once()
    client.twitch_streamer.close.assert_awaited_once()
    assert client.accounts_connected is False
    assert client.twitch_integration_enabled is False
