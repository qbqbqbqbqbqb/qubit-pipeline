from src.qubit.utils.log_utils import get_logger
from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from config.config import BOT_SCOPES, STREAMER_SCOPES

class TwitchWebsocketSub:

    def __init__(self):
        self.logger = get_logger(__name__)

    async def _subscribe_to_follow_events(self):
        try:
            self.logger.info("[_subscribe_to_follow_events] Subscribing to follow events...")

            try:
                users = []
                async for user in self.twitch_streamer.get_users(logins=[self.settings.twitch_channel]):
                    users.append(user)

            except Exception as e:
                self.logger.error(f"Error fetching users: {e}")
                return

            if not users:
                self.logger.error("No users found for given login")
                return

            user = users[0]
            broadcaster_id = user.id
            self.logger.info(f"Got broadcaster_id: {broadcaster_id}")

            method = self.eventsub.listen_channel_follow_v2
            self.logger.info(f"listen_channel_follow_v2 method: {method!r}")

            res = method(
                broadcaster_user_id=broadcaster_id,
                moderator_user_id=broadcaster_id,
                callback=self._on_follow
            )
            self.logger.info(f"Result of calling listen_channel_follow_v2: {res!r}")

            sub_id = await res
            self.logger.info(f"[_subscribe_to_follow_events] Follow subscription succeeded, id: {sub_id}")

        except Exception as e:
            self.logger.error(f"_subscribe_to_follow_events error: {e}")