from datetime import datetime, timezone

from twitchAPI.twitch import Twitch
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from config.config import BOT_SCOPES, STREAMER_SCOPES
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.oauth import UserAuthenticator, refresh_access_token
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelFollowEvent
from src.qubit.utils.log_utils import get_logger
from src.qubit.core.events import TwitchChatEvent, TwitchFollowEvent, TwitchRaidEvent, TwitchSubscriptionEvent


class TwitchEvents:

    def __init__(self):
        self.logger = get_logger(__name__)

    async def _setup_chat(self):
        """
        Set up chat monitoring for the Twitch channel.

        Creates a Chat instance, registers event handlers for ready and message events,
        and starts the chat monitoring.

        Returns:
            None
        """
        self.chat = await Chat(self.twitch_bot)
        self.chat.register_event(ChatEvent.READY, self._on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self._on_message)
        self.chat.register_event(ChatEvent.SUB, self._on_subscription)
        self.chat.register_event(ChatEvent.RAID, self._on_raid)
        self.chat.start()

    async def _on_subscription(self, event: EventData):
        if not self.subs_enabled.is_set():
            return
        try:
            self.logger.debug(f"Sub System Message {event.system_message}")
            self.logger.debug(f"Sub Plan Name {event.sub_plan_name}")
            self.logger.debug(f"Sub Type {event.sub_type}")           
            self.logger.debug(f"Sub Message{event.sub_message}")       

            user = "Someone" # was there an issue getting names for this before?
            tier = event.sub_plan_name
            sub_msg = event.sub_message
            sub_type = event.sub_type
            
            self.logger.info(f"Subscription event")

            event = TwitchSubscriptionEvent(
                type="twitch_subscription",
                data={"user": user, "tier": tier, "sub_type": sub_type, "sub_message": sub_msg},
                user=user,
                tier=tier,
                sub_type=sub_type,
                sub_message=sub_msg,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            self.event_bus.publish(event)

        except Exception as e:
            self.logger.error(f"[_on_subscription] Error handling subscription event: {e}")

    async def _on_raid(self, event: EventData):
        if not self.raid_enabled.is_set():
            return
        try:
            raider = event.get("from_broadcaster_user_name")
            viewers = event.get("viewers")
            message = f"{raider} is raiding with {viewers} viewers!"

            self.logger.info(f"Raid event: {message}")

            event = TwitchRaidEvent(
                type="twitch_raid",
                data={"user": raider, "viewers": viewers},
                user=raider,
                viewers=viewers,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            self.event_bus.publish(event)

        except Exception as e:
            self.logger.error(f"[_on_raid] Error handling raid event: {e}")

    async def _on_follow(self, event: ChannelFollowEvent):
        if not self.follow_enabled.is_set():
            return
        try:
            user = event.event.user_name
            broadcaster = event.event.broadcaster_user_name
            followed_at = event.event.followed_at

            message = f"{user} just followed the channel at {followed_at}!"

            self.logger.info(f"Follow event: {message}")

            event = TwitchFollowEvent(
                type="twitch_follow",
                data={"user": user, "followed_at": followed_at},
                user=user,
                followed_at=followed_at,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            self.event_bus.publish(event)

        except Exception as e:
            self.logger.error(f"[_on_follow] Error handling follow event: {e}")

    async def _on_ready(self, event: EventData):
            """
            Event handler called when the chat bot is ready.

            Joins the specified Twitch channel upon readiness.

            Args:
                event: EventData containing chat event information.

            Returns:
                None

            Raises:
                Exception: If joining the channel fails.
            """
            try:
                self.logger.info("[_on_ready] Bot ready, joining channel...")
                await event.chat.join_room(self.settings.twitch_channel)
                self.logger.info(f"[_on_ready] Joined channel: {self.settings.twitch_channel}")
            except Exception as e:
                self.logger.error(f"[_on_ready] Failed to join channel: {e}")

    async def _on_message(self, msg: ChatMessage):
        """
        Event handler for incoming chat messages.

        Processes chat messages, publishes them to the event broker,
        and queues filtered messages to memory if they pass content filters.

        Args:
            msg: ChatMessage object containing message details.

        Returns:
            None

        Raises:
            Exception: If message processing fails.
        """
        if not self.chat_enabled.is_set():
            return
        try:
            user = msg.user.name
            message = msg.text.strip()

            self.logger.debug(f"[_on_message] Message from {user}: {message}")

            event = TwitchChatEvent(
                type="twitch_chat",
                data={"user": user, "text": message},
                user=user,
                text=message,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
            self.logger.info("[_on_message] Chat message published to broker")

        except Exception as e:
            self.logger.error(f"[_on_message] Error handling message: {e}")

