"""
Pure Kick OAuth (no third-party library).

Handles interactive browser auth + token refresh using only stdlib + aiohttp.
Keeps the same interface expected by KickListener and the rest of the system.
"""

import asyncio
import base64
import hashlib
import logging
import os
import secrets
import webbrowser
from typing import Any, Optional, Tuple
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

KICK_AUTH_BASE = "https://id.kick.com"
KICK_API_BASE = "https://api.kick.com"

# Scopes we request for a typical input bot
BOT_SCOPES = ["user:read", "chat:write"]
STREAMER_SCOPES = ["user:read", "channel:read", "chat:write", "events:subscribe"]


class KickAuthMixin:
    """
    Mixin providing pure Kick OAuth (browser flow + refresh).
    Expects:
        self.settings (with kick_* fields)
        self.logger
    Sets:
        self.kick_bot
        self.kick_streamer   (these are now just dicts holding tokens)
    """

    logger: logging.Logger

    async def _authenticate_bot_account(self: Any) -> None:
        self.kick_bot = await self._get_or_authenticate_account(
            "bot",
            self.settings.kick_bot_oauth_token,
            self.settings.kick_bot_refresh_token,
            BOT_SCOPES,
        )

    async def _authenticate_streamer_account(self: Any) -> None:
        self.kick_streamer = await self._get_or_authenticate_account(
            "streamer",
            self.settings.kick_streamer_oauth_token,
            self.settings.kick_streamer_refresh_token,
            STREAMER_SCOPES,
        )

    async def _get_or_authenticate_account(
        self: Any, name: str, access_token: str, refresh_token: str, scopes: list[str]
    ) -> dict:
        if access_token and refresh_token:
            # Try to use existing tokens
            if await self._token_is_valid(access_token):
                return {"access_token": access_token, "refresh_token": refresh_token}
            # Try refresh
            try:
                new_access, new_refresh = await self._refresh_token(refresh_token)
                self._save_tokens(name, new_access, new_refresh)
                return {"access_token": new_access, "refresh_token": new_refresh}
            except Exception as e:
                self.logger.warning("[KickAuth] Refresh failed for %s: %s", name, e)

        # Interactive flow
        self.logger.info("[KickAuth] Starting interactive OAuth for %s account...", name)
        access, refresh = await self._run_interactive_auth(scopes)
        self._save_tokens(name, access, refresh)
        return {"access_token": access, "refresh_token": refresh}

    async def _token_is_valid(self, token: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{KICK_API_BASE}/public/v1/users",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _refresh_token(self, refresh_token: str) -> Tuple[str, str]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.kick_client_id,
            "client_secret": self.settings.kick_client_secret,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{KICK_AUTH_BASE}/oauth/token", data=data) as resp:
                body = await resp.text()
                if resp.status != 200:
                    self.logger.error("[KickAuth] Refresh failed. Status=%s Body=%s", resp.status, body)
                    raise Exception(f"Refresh failed: status={resp.status} body={body}")
                j = await resp.json()
                return j["access_token"], j.get("refresh_token", refresh_token)

    async def _run_interactive_auth(self, scopes: list[str]) -> Tuple[str, str]:
        """Runs a one-time local server + browser flow."""
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip("=")

        state = secrets.token_urlsafe(16)
        redirect_uri = self.settings.kick_redirect_uri or "http://localhost:36571"

        params = {
            "client_id": self.settings.kick_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        auth_url = f"{KICK_AUTH_BASE}/oauth/authorize?{urlencode(params)}"

        self.logger.info("[KickAuth] Opening browser for authorization...")
        webbrowser.open(auth_url)

        # Tiny local server to catch the redirect
        received_code: dict[str, Optional[str]] = {"code": None, "state": None}

        async def handle(request):
            received_code["code"] = request.query.get("code")
            received_code["state"] = request.query.get("state")
            return web.Response(text="Authorization complete. You can close this tab.")

        app = web.Application()
        app.router.add_get("/", handle)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 36571)
        await site.start()

        try:
            # Wait for the redirect (with timeout)
            for _ in range(120):  # 2 minutes
                if received_code["code"]:
                    break
                await asyncio.sleep(1)
            else:
                raise TimeoutError("Authorization timed out")

            if received_code["state"] != state:
                raise Exception("State mismatch")

            # Exchange code
            data = {
                "grant_type": "authorization_code",
                "client_id": self.settings.kick_client_id,
                "client_secret": self.settings.kick_client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
                "code": received_code["code"],
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{KICK_AUTH_BASE}/oauth/token", data=data) as resp:
                    body = await resp.text()
                    if resp.status != 200:
                        self.logger.error("[KickAuth] Token exchange failed. Status=%s Body=%s", resp.status, body)
                        raise Exception(f"Token exchange failed: status={resp.status} body={body}")
                    try:
                        j = await resp.json()
                    except Exception:
                        j = {"raw": body}
                    return j.get("access_token"), j.get("refresh_token", "")
        finally:
            await runner.cleanup()

    def _save_tokens(self, account: str, access: str, refresh: str):
        if account == "bot":
            self.settings.kick_bot_oauth_token = access
            self.settings.kick_bot_refresh_token = refresh
        else:
            self.settings.kick_streamer_oauth_token = access
            self.settings.kick_streamer_refresh_token = refresh
        self.settings.save()
        self.logger.info("[KickAuth] Saved new %s tokens", account)

    async def _refresh_tokens(self: Any) -> None:
        """Called periodically by the listener."""
        try:
            if self.settings.kick_bot_refresh_token:
                new_access, new_refresh = await self._refresh_token(
                    self.settings.kick_bot_refresh_token
                )
                self.settings.kick_bot_oauth_token = new_access
                self.settings.kick_bot_refresh_token = new_refresh
                self.settings.save()

            if self.settings.kick_streamer_refresh_token:
                new_access, new_refresh = await self._refresh_token(
                    self.settings.kick_streamer_refresh_token
                )
                self.settings.kick_streamer_oauth_token = new_access
                self.settings.kick_streamer_refresh_token = new_refresh
                self.settings.save()
        except Exception as e:
            self.logger.warning("[KickAuth] Token refresh failed: %s", e)
