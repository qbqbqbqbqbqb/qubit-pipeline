import aiohttp
import os
from dotenv import load_dotenv
load_dotenv()

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("RefreshToken")

def update_env_var(key, value, env_path=".env"):
    """
    Updates or adds an environment variable in the specified .env file.

    Args:
        key (str): Environment variable name.
        value (str): Value to set.
        env_path (str, optional): Path to the .env file. Defaults to ".env".
    """
    lines = []

    if os.path.exists(env_path):
        with open(env_path, "r") as file:
            lines = file.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w") as file:
        file.writelines(lines)

    logger.debug(f"[.env] Updated {key}")

async def refresh_twitch_token():
    """
    Refreshes the Twitch OAuth tokens asynchronously for both bot and streamer accounts,
    updates environment variables, and persists them in the .env file.
    """

    logger.info("Starting refresh_twitch_token() for dual accounts")

    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")

    token_url = "https://id.twitch.tv/oauth2/token"

    bot_refresh_token = os.getenv("BOT_REFRESH_TOKEN")
    if bot_refresh_token:
        logger.info("[Token Refresh] Refreshing bot account tokens...")
        try:
            bot_params = {
                "grant_type": "refresh_token",
                "refresh_token": bot_refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, params=bot_params) as response:
                    logger.info(f"[Bot Token] HTTP Status: {response.status}")
                    data = await response.json()

                    if "access_token" in data:
                        logger.debug("[Bot Token] Refreshed successfully")
                        new_access_token = data["access_token"]
                        new_refresh_token = data.get("refresh_token", bot_refresh_token)

                        os.environ["BOT_OAUTH_TOKEN"] = new_access_token
                        os.environ["BOT_REFRESH_TOKEN"] = new_refresh_token

                        update_env_var("BOT_OAUTH_TOKEN", new_access_token)
                        update_env_var("BOT_REFRESH_TOKEN", new_refresh_token)
                        logger.info("[Bot Token] Tokens updated successfully")
                    else:
                        logger.error(f"[Bot Token] Refresh failed: {data}")
        except Exception as e:
            logger.error(f"[Bot Token] Error refreshing bot tokens: {e}")
    else:
        logger.warning("[Bot Token] No BOT_REFRESH_TOKEN found, skipping bot token refresh")

    streamer_refresh_token = os.getenv("STREAMER_REFRESH_TOKEN")
    if streamer_refresh_token:
        logger.info("[Token Refresh] Refreshing streamer account tokens...")
        try:
            streamer_params = {
                "grant_type": "refresh_token",
                "refresh_token": streamer_refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, params=streamer_params) as response:
                    logger.info(f"[Streamer Token] HTTP Status: {response.status}")
                    data = await response.json()

                    if "access_token" in data:
                        logger.debug("[Streamer Token] Refreshed successfully")
                        new_access_token = data["access_token"]
                        new_refresh_token = data.get("refresh_token", streamer_refresh_token)

                        os.environ["STREAMER_OAUTH_TOKEN"] = new_access_token
                        os.environ["STREAMER_REFRESH_TOKEN"] = new_refresh_token

                        update_env_var("STREAMER_OAUTH_TOKEN", new_access_token)
                        update_env_var("STREAMER_REFRESH_TOKEN", new_refresh_token)
                        logger.info("[Streamer Token] Tokens updated successfully")
                    else:
                        logger.error(f"[Streamer Token] Refresh failed: {data}")
        except Exception as e:
            logger.error(f"[Streamer Token] Error refreshing streamer tokens: {e}")
    else:
        logger.info("[Streamer Token] No STREAMER_REFRESH_TOKEN found, skipping streamer token refresh")

    if not bot_refresh_token and not streamer_refresh_token:
        logger.warning("[Token Refresh] No refresh tokens found for either account")
        raise Exception("No refresh tokens available for token refresh")

    logger.info("[Token Refresh] Dual-account token refresh completed")
