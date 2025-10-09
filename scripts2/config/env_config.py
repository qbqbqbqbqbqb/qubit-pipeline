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


settings = Settings()
