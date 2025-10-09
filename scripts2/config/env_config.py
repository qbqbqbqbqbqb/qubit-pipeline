from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
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
    obs_host: str
    obs_port: str
    obs_password: str

    model_config = ConfigDict(env_file=".env")

    def save(self):
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

        new_lines = [f"{k}={v}" for k, v in new_env.items()]
        env_path.write_text("\n".join(new_lines))


settings = Settings()
