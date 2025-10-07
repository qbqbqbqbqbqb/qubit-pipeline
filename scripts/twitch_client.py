import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatEvent, EventData, ChatMessage, ChatSub
from twitchAPI.oauth import UserAuthenticator

class TwitchClient:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger

        self.twitch_bot = None
        self.twitch_streamer = None
        self.chat = None
        self.accounts_connected = False

        self.bot_scopes = [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT
        ]

        self.streamer_scopes = [
            AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
            AuthScope.CHANNEL_MANAGE_RAIDS
        ]

    async def start(self) -> bool:
        self.logger.info("[start] Starting TwitchClient...")
        try:
            await self._authenticate_bot_account()
            await self._authenticate_streamer_account()
            await self._setup_chat()
            self.accounts_connected = True
            self.logger.info(f"[start] Connected to Twitch channel: {self.settings.twitch_channel}")
            return True
        except Exception as e:
            self.logger.error(f"[start] Failed to connect TwitchClient: {e}")
            return False

    async def _authenticate_bot_account(self):
        self.logger.info("[_authenticate_bot_account] Authenticating bot account...")
        self.twitch_bot = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
        if not self.settings.bot_oauth_token:
            self.logger.info("[_authenticate_bot_account] No bot OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, self.bot_scopes)
            token, refresh_token = await auth.authenticate()
            self.settings.bot_oauth_token = token
            self.settings.bot_refresh_token = refresh_token

        await self.twitch_bot.set_user_authentication(
            self.settings.bot_oauth_token,
            self.bot_scopes,
            self.settings.bot_refresh_token
        )


    async def _authenticate_streamer_account(self):
        if self.settings.streamer_oauth_token and self.settings.streamer_refresh_token:
            self.logger.info("[_authenticate_streamer_account] Authenticating streamer account...")
            self.twitch_streamer = Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
            if not self.settings.bot_oauth_token:
                self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
                auth = UserAuthenticator(self.twitch_bot, self.streamer_scopes)
                token, refresh_token = await auth.authenticate()
                self.settings.streamer_oauth_token = token
                self.settings.streamer_refresh_token = refresh_token

            await self.twitch_streamer.set_user_authentication(
                self.settings.streamer_oauth_token,
                self.streamer_scopes,
                self.settings.streamer_refresh_token
            )

    async def _setup_chat(self):
        self.chat = await Chat(self.twitch_bot)
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
        self.chat.register_event(ChatEvent.SUB, self._on_subscription)
        self.chat.register_event(ChatEvent.RAID, self._on_raid)
        self.chat.start()

    async def _on_ready(self, event: EventData):
        try:
            self.logger.info("[_on_ready] Bot ready, joining channel...")
            await event.chat.join_room(self.settings.twitch_channel)
            self.logger.info(f"[_on_ready] Joined channel: {self.settings.twitch_channel}")
        except Exception as e:
            self.logger.error(f"[_on_ready] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        """Handle incoming chat messages."""
        try:
            author = msg.user.name
            content = msg.text.strip()

            if not content:
                return

            self.logger.debug(f"[_on_message] Message from {author}: {content}")

            bits = msg.tags.get('bits') 
            if bits:
                await self.chat.send_message(f"Thanks {author} for cheering {bits} bits! 🎉")
        except Exception as e:
            self.logger.error(f"[_on_message] Error handling message: {e}")

    async def _on_subscription(self, sub: ChatSub):
        """Handle subscription events."""
        try:
            self.logger.info(f"[_on_subscription] New subscription in {sub.room.name}: {sub.sub_plan}")
        except Exception as e:
            self.logger.error(f"[_on_subscription] Error handling subscription: {e}")

    async def _on_raid(self, raid_event: EventData):
        """Handle raid events."""
        try:
            raider_name = getattr(raid_event, 'from_broadcaster_user_name', 'unknown')
            viewer_count = getattr(raid_event, 'viewers', 0)
            self.logger.info(f"[_on_raid] Raid from {raider_name} with {viewer_count} viewers")

        except Exception as e:
            self.logger.error(f"[_on_raid] Error handling raid: {e}")

    async def disconnect(self):
        self.logger.info("[disconnect] Disconnecting TwitchClient...")
        if self.chat is not None:
            self.chat.stop()
        if self.twitch_bot:
            await self.twitch_bot.close()
        if self.twitch_streamer:
            await self.twitch_streamer.close()
        self.accounts_connected = False
        self.logger.info("[disconnect] Disconnected successfully.")
