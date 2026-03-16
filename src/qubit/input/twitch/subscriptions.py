from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.twitch import Twitch  # for twitch_streamer
import logging
from config.env_config import Settings

class TwitchWebsocketSubMixin:

    logger: logging.Logger
    twitch_streamer: Twitch
    eventsub: EventSubWebsocket
    settings: Settings   
    _on_follow: callable

    async def _subscribe_to_follow_events(self):
        try:
            self.logger.info("Subscribing to follow events...")

            if not self.twitch_streamer or not self.eventsub:
                self.logger.error("Twitch client not initialized before subscribing")
                return

            broadcaster_id = None
            async for user in self.twitch_streamer.get_users(
                logins=[self.settings.twitch_channel]
            ):
                broadcaster_id = user.id
                break

            if not broadcaster_id:
                self.logger.error("No users found for given login")
                return

            self.logger.info(f"Got broadcaster_id: {broadcaster_id}")

            sub_id = await self.eventsub.listen_channel_follow_v2(
                broadcaster_user_id=broadcaster_id,
                moderator_user_id=broadcaster_id,
                callback=self._on_follow
            )

            self.logger.info(f"Follow subscription succeeded, id: {sub_id}")

        except Exception as e:
            self.logger.error(f"_subscribe_to_follow_events error: {e}")