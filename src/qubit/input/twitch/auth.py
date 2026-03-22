"""
Twitch authentication utilities.

This module provides the ``TwitchAuthMixin`` which encapsulates authentication
logic for Twitch API access. It supports both bot and streamer accounts and
handles initial OAuth authentication as well as token refreshing.

The mixin expects the consuming class to provide:

- ``self.settings``: configuration object containing Twitch credentials
  and stored OAuth tokens.
- ``self.logger``: a configured ``logging.Logger`` instance.

Responsibilities
----------------
- Authenticate bot and streamer Twitch accounts.
- Reuse stored OAuth tokens when available.
- Perform interactive OAuth authentication when tokens are missing.
- Refresh expired access tokens using stored refresh tokens.
- Persist updated credentials via the settings object.
"""
import asyncio
import logging
from typing import Any
import aiohttp
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from config.config import BOT_SCOPES, STREAMER_SCOPES

class TwitchAuthMixin:
    """
    Mixin providing Twitch API authentication functionality.

    This mixin handles authentication for both a bot account and a streamer
    account using the Twitch OAuth flow. It manages token retrieval,
    reuse of stored tokens, and refreshing expired tokens.

    Expected attributes
    -------------------
    logger : logging.Logger
        Logger used for authentication status and error reporting.

    settings : object
        Configuration object containing Twitch credentials and token storage.
        Expected fields include client ID, client secret, redirect URI,
        OAuth tokens, and refresh tokens.
    """
    logger: logging.Logger

    async def _authenticate_bot_account(self: Any) -> None:
        """
        Authenticate the bot Twitch account.

        Creates a Twitch client and attempts to authenticate using stored
        OAuth tokens. If tokens are missing, an interactive OAuth flow is
        initiated to obtain new access and refresh tokens.

        The resulting tokens are stored in the settings object.

        Raises
        ------
        Exception
            If authentication fails or the OAuth flow cannot complete.
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


    async def _authenticate_streamer_account(self: Any) -> None:
        """
        Authenticate the streamer Twitch account.

        Creates a Twitch client and attempts to authenticate using stored
        OAuth tokens. If tokens are missing, an interactive OAuth flow is
        initiated to obtain new access and refresh tokens.

        The resulting tokens are stored in the settings object.

        Raises
        ------
        Exception
            If authentication fails or the OAuth flow cannot complete.
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


# TODO cgheck if this works
    """     async def _authenticate_twitch_accounts(self: Any, client_attr: str, token_attr: str, refresh_token_attr: str, account_type: str, scopes: list) -> None:
            self.twitch_account = await Twitch(self.settings.twitch_client_id, self.settings.twitch_client_secret)
            setattr(self, client_attr, self.twitch_account)
            
            token = getattr(self.settings, token_attr)
            refresh_token = getattr(self.settings, refresh_token_attr)

            if not token or not refresh_token:
                self.logger.info("[_authenticate_twitch_accounts] No %s found, authenticating interactively...", account_type)
                auth = UserAuthenticator(self.twitch_account, scopes, url=self.settings.twitch_redirect_uri)
                token, refresh_token = await auth.authenticate()
                setattr(self.settings, token_attr, token)
                setattr(self.settings, refresh_token_attr, refresh_token)
            else:
                await setattr(token, scopes, refresh_token)
    """

    async def _refresh_tokens(self: Any) -> None:
        """
        Refresh OAuth access tokens for bot and streamer accounts.

        Uses stored refresh tokens to obtain new access tokens from Twitch.
        Updated tokens are written back to the settings object and persisted.

        If a refresh token is missing for an account, that account is skipped.

        Errors are logged but do not propagate unless the refresh process
        fails unexpectedly.
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

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.logger.error("[_refresh_tokens] Network error refreshing tokens: %s", e)

        except ValueError as e:
            self.logger.error("[_refresh_tokens] Invalid token response: %s", e)

        except Exception as e:
            self.logger.error("[_refresh_tokens] Unexpected error refreshing tokens:%s", e)
