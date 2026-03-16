import logging
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.twitch import Twitch
from twitchAPI.twitch import TwitchAPIException

from config.env_config import Settings

class TwitchWebsocketSubMixin:
    """
    Mixin providing Twitch EventSub WebSocket subscription functionality.

    Designed to be used with a class that initializes Twitch clients, this mixin
    handles subscribing to channel follow events via Twitch's EventSub WebSocket API.

    Attributes:
        logger (logging.Logger): Logger instance for reporting subscription status and errors.
        twitch_streamer (Twitch): Authenticated Twitch client representing the streamer.
        eventsub (EventSubWebsocket): EventSub WebSocket client used to listen to Twitch events.
        settings (Settings): Pydantic settings instance containing Twitch channel configuration.
        _on_follow (Callable[[object], None]): Callback function to invoke when a follow event occurs.

    Methods:
        _subscribe_to_follow_events(): Asynchronously subscribes to follow events for the configured Twitch channel.
            Logs subscription success or errors.
    
    Notes:
        - The class expects that `twitch_streamer` and `eventsub` are properly initialized
          before calling `_subscribe_to_follow_events()`.
        - Intended to be used as a mixin in combination with a service class managing
          Twitch authentication and event loops.
    """

    logger: logging.Logger
    twitch_streamer: Twitch
    eventsub: EventSubWebsocket
    settings: Settings
    _on_follow: callable

    async def _subscribe_to_follow_events(self):
        try:
            self.logger.info("[_subscribe_to_follow_events] Subscribing to follow events...")

            if not self.twitch_streamer or not self.eventsub:
                self.logger.error("[_subscribe_to_follow_events] Twitch client not initialized before subscribing")
                return

            broadcaster_id = None
            async for user in self.twitch_streamer.get_users(
                logins=[self.settings.twitch_channel]
            ):
                broadcaster_id = user.id
                break

            if not broadcaster_id:
                self.logger.error("[_subscribe_to_follow_events] No users found for given login")
                return

            self.logger.info("[_subscribe_to_follow_events] Got broadcaster_id: %s", broadcaster_id)

            sub_id = await self.eventsub.listen_channel_follow_v2(
                broadcaster_user_id=broadcaster_id,
                moderator_user_id=broadcaster_id,
                callback=self._on_follow
            )

            self.logger.info("[_subscribe_to_follow_events] Follow subscription succeeded, id: %s", sub_id)

        except (TwitchAPIException) as e:
            self.logger.error("[_subscribe_to_follow_events] Twitch error: %s", e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("[_subscribe_to_follow_events] unexpected error: %s", e)
