from src.utils.log_utils import get_logger
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from config.config import BOT_SCOPES, STREAMER_SCOPES

class TwitchAuth:

    def __init__(self):
        self.logger = get_logger(__name__)
        
    async def _authenticate_bot_account(self):
        """
        Authenticate the bot account with Twitch API.

        Creates a Twitch client for the bot, checks for existing tokens,
        and performs interactive authentication if needed.

        Returns:
            None

        Raises:
            Exception: If authentication fails.
        """
        self.twitch_bot = await Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)

        if not self.settings.bot_oauth_token or not self.settings.bot_refresh_token:
            self.logger.info("[_authenticate_bot_account] No bot OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_bot, BOT_SCOPES, url=self.settings.twitch_redirect_uri)
            token, refresh_token = await auth.authenticate()
            self.settings.bot_oauth_token = token
            self.settings.bot_refresh_token = refresh_token
        else:
            await self.twitch_bot.set_user_authentication(
                self.settings.bot_oauth_token,
                BOT_SCOPES,
                self.settings.bot_refresh_token
            )

    async def _authenticate_streamer_account(self):
        """
        Authenticate the streamer account with Twitch API.

        Creates a Twitch client for the streamer, checks for existing tokens,
        and performs interactive authentication if needed.

        Returns:
            None

        Raises:
            Exception: If authentication fails.
        """
        self.twitch_streamer = await Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)

        if not self.settings.streamer_oauth_token or not self.settings.streamer_refresh_token:
            self.logger.info("[_authenticate_streamer_account] No streamer OAuth token found, authenticating interactively...")
            auth = UserAuthenticator(self.twitch_streamer, STREAMER_SCOPES, url=self.settings.twitch_redirect_uri)
            token, refresh_token = await auth.authenticate()
            self.settings.streamer_oauth_token = token
            self.settings.streamer_refresh_token = refresh_token
        else:
            await self.twitch_streamer.set_user_authentication(
                self.settings.streamer_oauth_token,
                STREAMER_SCOPES,
                self.settings.streamer_refresh_token
            )

    async def _refresh_tokens(self):
        """
        Refresh authentication tokens for bot and streamer accounts.

        Uses refresh tokens to obtain new access tokens and updates settings.
        Saves the updated tokens to persistent storage.

        Returns:
            None

        Raises:
            Exception: If token refresh fails.
        """
        try:
            self.logger.info("[_refresh_tokens] Refreshing tokens...")

            if self.settings.bot_refresh_token:
                new_token, new_refresh = await refresh_access_token(
                    self.settings.bot_refresh_token,
                    self.settings.twitch_client_id,
                    self.settings.twitch_client_secret
                )
                self.settings.bot_oauth_token = new_token
                self.settings.bot_refresh_token = new_refresh
                self.logger.info("[_refresh_tokens] Bot tokens refreshed")

            if self.settings.streamer_refresh_token:
                new_token, new_refresh = await refresh_access_token(
                    self.settings.streamer_refresh_token,
                    self.settings.twitch_client_id,
                    self.settings.twitch_client_secret
                )
                self.settings.streamer_oauth_token = new_token
                self.settings.streamer_refresh_token = new_refresh
                self.logger.info("[_refresh_tokens] Streamer tokens refreshed")

            self.settings.save()
        except Exception as e:
            self.logger.error(f"[_refresh_tokens] Error refreshing tokens: {e}")