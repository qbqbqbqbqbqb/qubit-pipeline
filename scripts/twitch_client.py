import asyncio
import os
from dotenv import load_dotenv
import datetime

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand

from scripts.utils.log_utils import get_logger
logger = get_logger("TwitchClient")

class TwitchClient():
    def __init__(self):

        self.twitch_integration_enabled = False
        self.accounts_connected = False

        load_dotenv()
        self.app_id = os.getenv("TWITCH_CLIENT_ID")
        self.app_secret = os.getenv("TWITCH_CLIENT_SECRET")

        self.bot_oauth_token = os.getenv("BOT_OAUTH_TOKEN") or os.getenv("TWITCH_OAUTH_TOKEN")
        self.bot_refresh_token = os.getenv("BOT_REFRESH_TOKEN") or os.getenv("TWITCH_REFRESH_TOKEN")

        self.streamer_oauth_token = os.getenv("STREAMER_OAUTH_TOKEN")
        self.streamer_refresh_token = os.getenv("STREAMER_REFRESH_TOKEN")

        self.channel_name = os.getenv("TWITCH_CHANNEL")
        self.redirect_uri = os.getenv("TWITCH_REDIRECT_URI", "http://localhost")

        self.bot_scopes = [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT
        ]

        self.streamer_scopes = [
            AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
            AuthScope.CHANNEL_MANAGE_RAIDS
        ]

    async def start(self):
        self.twitch_integration_enabled = True
        return await self.connect()

    async def _register_event_handlers(self, chat):
        chat.register_event(ChatEvent.READY, self._on_ready)
        chat.register_event(ChatEvent.MESSAGE, self._on_message)
        chat.register_event(ChatEvent.SUB, self._on_subscription)
        self.chat.register_event(ChatEvent.RAID, self._on_raid)
    
    async def connect(self) -> bool:
        """
        Establish connection to Twitch API with dual-account authentication.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("[TwitchClient] Initializing dual-account Twitch API connection...")

            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._setup_chat()

            logger.info(f"[TwitchClient] Connected to Twitch channel: {self.channel_name}")
            logger.info("[TwitchClient] Chat operations: bot account | Event monitoring: streamer account" if self.twitch_streamer else "[TwitchClient] All operations: bot account")
            self.accounts_connected = True
            return True

        except Exception as e:
            logger.error(f"[TwitchClient] Failed to connect to Twitch: {e}")
            return False

    async def _authenticate_bot_account(self):
        """Authenticate the bot account for chat operations."""
        logger.info("[TwitchClient] Authenticating bot account...")
        self.twitch_bot = Twitch(self.app_id, self.app_secret)

        if self.bot_oauth_token and self.bot_refresh_token:
            try:
                await self.twitch_bot.set_user_authentication(self.bot_oauth_token, self.bot_scopes, self.bot_refresh_token)
                users = []
                async for user in self.twitch_bot.get_users():
                    users.append(user)
                    break
                if users:
                    logger.info("[TwitchClient] Bot account authenticated successfully")
                else:
                    raise Exception("Bot token validation failed")
            except Exception as e:
                logger.warning(f"[TwitchClient] Bot tokens failed ({str(e)}), attempting OAuth...")
                self.authenticator_bot = UserAuthenticator(self.twitch_bot, self.bot_scopes, url=self.redirect_uri)
                token, refresh_token = await self.authenticator_bot.authenticate()
                await self.twitch_bot.set_user_authentication(token, self.bot_scopes, refresh_token)
                logger.info("[TwitchClient] Bot OAuth authentication completed")
        else:
            logger.info("[TwitchClient] No bot tokens found, using OAuth flow...")
            self.authenticator_bot = UserAuthenticator(self.twitch_bot, self.bot_scopes, url=self.redirect_uri)
            token, refresh_token = await self.authenticator_bot.authenticate()
            await self.twitch_bot.set_user_authentication(token, self.bot_scopes, refresh_token)

    async def _authenticate_streamer_account(self):
        """Authenticate the streamer account for event operations."""
        if self.streamer_oauth_token and self.streamer_refresh_token:
            logger.info("[TwitchClient] Authenticating streamer account for events...")
            self.twitch_streamer = Twitch(self.app_id, self.app_secret)

            try:
                await self.twitch_streamer.set_user_authentication(self.streamer_oauth_token, self.streamer_scopes, self.streamer_refresh_token)
                users = []
                async for user in self.twitch_streamer.get_users():
                    users.append(user)
                    break
                if users:
                    logger.info("[TwitchClient] Streamer account authenticated successfully")
                else:
                    raise Exception("Streamer token validation failed")
            except Exception as e:
                logger.warning(f"[TwitchClient] Streamer tokens failed ({str(e)}), will use bot account for events")
                self.twitch_streamer = None
        else:
            logger.info("[TwitchClient] No streamer tokens provided, using bot account for events")
            self.twitch_streamer = None

    async def _setup_chat(self):
        """Set up the chat instance and start it."""
        self.chat = await Chat(self.twitch_bot)
        await self._register_event_handlers(self.chat)
        self.chat.start()
                
    async def _on_ready(self, ready_event: EventData):
        """Handle bot ready event."""
        logger.info("[TwitchClient] Bot is ready, joining channel...")
        try:
            await ready_event.chat.join_room(self.channel_name)
            logger.info(f"[TwitchClient] Joined channel: {self.channel_name}")
        except Exception as e:
            logger.error(f"[TwitchClient] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        """Handle incoming chat messages."""
        try:
            author = msg.user.name
            content = msg.text.strip()

            if not content:
                return

            logger.debug(f"[TwitchClient] Message from {author}: {content}")

        except Exception as e:
            logger.error(f"[TwitchClient] Error handling message: {e}")

    async def _on_subscription(self, sub: ChatSub):
        """Handle subscription events."""
        try:
            logger.info(f"[TwitchClient] New subscription in {sub.room.name}: {sub.sub_plan}")
        except Exception as e:
            logger.error(f"[TwitchClient] Error handling subscription: {e}")

    async def _on_raid(self, raid_event: EventData):
        """Handle raid events."""
        try:
            raider_name = getattr(raid_event, 'from_broadcaster_user_name', 'unknown')
            viewer_count = getattr(raid_event, 'viewers', 0)
            logger.info(f"[TwitchClient] Raid from {raider_name} with {viewer_count} viewers")

        except Exception as e:
            logger.error(f"[TwitchClient] Error handling raid: {e}")

    async def disconnect(self):
        """Disconnect from Twitch and clean up resources."""
        logger.info("[TwitchClient] Disconnecting from Twitch...")

        try:
            if self.twitch_bot:
                await self.twitch_bot.close()

            if self.twitch_streamer:
                await self.twitch_streamer.close()

            self.accounts_connected = False
            self.twitch_integration_enabled = False
            logger.info("[TwitchClient] Disconnected successfully")

        except Exception as e:
            logger.error(f"[TwitchClient] Error during disconnect: {e}")
