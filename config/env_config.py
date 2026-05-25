"""
Environment configuration module using Pydantic for settings management.

This module defines the Settings class for loading and saving environment variables
from a .env file, including Twitch API credentials, OBS settings, and tokens.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    """
    Pydantic settings class for environment configuration.

    Loads settings from a .env file and provides a method to save updated tokens back to the file.
    Includes Twitch and Kick API credentials, OBS connection details, and authentication tokens.
    """
    # ===================== MODEL SELECTION =====================
    active_model: str = "stheno"
    main_formatter: str | None = None
    reflection_formatter: str | None = None

    # Per-profile generation overrides (optional - higher precedence than model defaults)
    main_temperature: float | None = None
    main_top_p: float | None = None
    reflection_temperature: float | None = None
    reflection_top_p: float | None = None

    twitch_client_id: str
    twitch_client_secret: str
    bot_oauth_token: str
    bot_refresh_token: str
    streamer_oauth_token: str
    streamer_refresh_token: str
    twitch_channel: str
    twitch_redirect_uri: str
    twitch_streamer_name: str
    twitch_bot_name: str
    token_endpoint: str
    # ===================== KICK (pure HTTP) =====================
    kick_client_id: str = ""
    kick_client_secret: str = ""
    kick_bot_oauth_token: str = ""
    kick_bot_refresh_token: str = ""
    kick_streamer_oauth_token: str = ""
    kick_streamer_refresh_token: str = ""
    kick_channel: str = ""
    kick_chatroom_id: int | None = None   # optional manual override
    kick_redirect_uri: str = ""
    kick_streamer_name: str = ""
    kick_bot_name: str = ""
    audio_directory: str = "audio"   # folder containing pre-converted RVC singing files
    obs_host: str
    obs_port: str
    obs_password: str

    model_config = ConfigDict(env_file=".env")

    def save(self):
        """
        Saves updated OAuth tokens back to the .env file.

        Reads the existing .env file, updates the token fields with current values,
        and writes the updated content back to the file.
        """
        env_path = Path(self.model_config['env_file'])
        env_vars = env_path.read_text().splitlines()
 
        new_env = {}
        for line in env_vars:
            if line.strip() == "" or line.strip().startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                new_env[k.strip()] = v.strip()
 
        new_env["BOT_OAUTH_TOKEN"] = self.bot_oauth_token
        new_env["BOT_REFRESH_TOKEN"] = self.bot_refresh_token
        new_env["STREAMER_OAUTH_TOKEN"] = self.streamer_oauth_token
        new_env["STREAMER_REFRESH_TOKEN"] = self.streamer_refresh_token
        new_env["KICK_BOT_OAUTH_TOKEN"] = self.kick_bot_oauth_token
        new_env["KICK_BOT_REFRESH_TOKEN"] = self.kick_bot_refresh_token
        new_env["KICK_STREAMER_OAUTH_TOKEN"] = self.kick_streamer_oauth_token
        new_env["KICK_STREAMER_REFRESH_TOKEN"] = self.kick_streamer_refresh_token

        new_lines = [f"{k}={v}" for k, v in new_env.items()]
        env_path.write_text("\n".join(new_lines))


settings = Settings()
