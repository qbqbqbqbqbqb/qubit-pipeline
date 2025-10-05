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
    Refreshes the Twitch OAuth token asynchronously using the refresh token, updates environment variables, and persists them in the .env file.
    """

    logger.info("Starting refresh_twitch_token()")
    
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    refresh_token = os.getenv("TWITCH_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError("One or more required environment variables are missing or None")

    token_url = "https://id.twitch.tv/oauth2/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, params=params) as response:
            logger.info(f"HTTP Status: {response.status}")
            data = await response.json()
            #logger.info(f"Twitch token response: {data}")
            # this will show token in terminal if uncommented
            if "access_token" in data:
                logger.debug("[Token Refreshed]")
                new_access_token = data["access_token"]
                new_refresh_token = data.get("refresh_token", refresh_token)

                os.environ["TWITCH_OAUTH_TOKEN"] = new_access_token
                os.environ["TWITCH_REFRESH_TOKEN"] = new_refresh_token

                update_env_var("TWITCH_OAUTH_TOKEN", new_access_token)
                update_env_var("TWITCH_REFRESH_TOKEN", new_refresh_token)

            else:
                logger.critical(f"[Token Refresh Failed] {data}")
                raise Exception("Failed to refresh Twitch token")
