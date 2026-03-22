"""Twitch event handling mixin for chat and EventSub integration.

This module provides TwitchEventsMixin, a mixin class designed to add
Twitch chat and EventSub event handling capabilities to a Twitch bot
application. It manages the following responsibilities:

- Monitors Twitch chat messages using the Twitch Chat API.
- Registers handlers for chat messages, subscriptions, raids, and follows.
- Converts Twitch API events into internal event objects:
  TwitchChatEvent, TwitchFollowEvent, TwitchRaidEvent, TwitchSubscriptionEvent.
- Publishes these internal events to the application's event bus for
  downstream processing.
- Logs detailed debug and info messages for each event type.

The mixin is intended to be combined with a bot or application class
that provides access to an authenticated Twitch client (`twitch_bot`),
application state, and an event bus.

Classes:
    TwitchEventsMixin: Adds Twitch chat and EventSub event handling to a bot.

Usage example:
    class MyTwitchBot(TwitchEventsMixin, SomeBotBaseClass):
        async def start(self):
            await self._setup_chat()
"""
from datetime import datetime, timezone
import logging
from typing import Any

from twitchAPI.type import ChatEvent
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.object.eventsub import ChannelFollowEvent
from twitchAPI.twitch import Twitch

from src.qubit.core.events import (TwitchChatEvent,
    TwitchFollowEvent, TwitchRaidEvent, TwitchSubscriptionEvent)

class TwitchEventsMixin:
    """
    Mixin providing Twitch chat and EventSub event handling for a Twitch bot.

    Responsibilities:
        - Set up chat monitoring via the Twitch Chat API.
        - Register event handlers for subscriptions, raids, follows, and messages.
        - Convert Twitch API events into internal event objects 
          (TwitchChatEvent, TwitchFollowEvent, etc.)
          and publish them to the application's event bus.

    Attributes:
        logger (logging.Logger): Logger for debug and info messages.
        twitch_bot (Twitch): Authenticated Twitch bot client.
        app (Any): Application instance containing state and event bus.
    """
    logger: logging.Logger
    twitch_bot: Twitch
    app: any


    async def _setup_chat(self: Any) -> None:
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

    async def _on_subscription(self: Any, event: EventData) -> None:
        subs_enabled = self.app.state.features.get("subs", True)
        if not subs_enabled:
            return
        try:
            self.logger.debug("[_on_subscription] Sub System Message: %s", event.system_message)
            self.logger.debug("[_on_subscription] Sub Plan Name: %s", event.sub_plan_name)
            self.logger.debug("[_on_subscription] Sub Type: %s", event.sub_type)
            self.logger.debug("[_on_subscription] Sub Message: %s", event.sub_message)

            user = "Someone" # was there an issue getting names for this before?
            tier = event.sub_plan_name
            sub_msg = event.sub_message
            sub_type = event.sub_type

            self.logger.info("[_on_subscription] Subscription event: %s", event)

            event = TwitchSubscriptionEvent(
                type="twitch_subscription",
                data={"user": user, "tier": tier, "sub_type": sub_type, "sub_message": sub_msg},
                user=user,
                tier=tier,
                sub_type=sub_type,
                sub_message=sub_msg,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(f"[_on_subscription] Error handling subscription event: {e}")

    async def _on_raid(self: Any, event: EventData) -> None:
        raid_enabled = self.app.state.features.get("raid", True)
        if not raid_enabled:
            return
        try:
            raider = event.get("from_broadcaster_user_name")
            viewers = event.get("viewers")
            message = f"{raider} is raiding with {viewers} viewers!"

            self.logger.info("[_on_raid] Raid event: %s", message)

            event = TwitchRaidEvent(
                type="twitch_raid",
                data={"user": raider, "viewers": viewers},
                user=raider,
                viewers=viewers,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("[_on_raid] Error handling raid event: %s", e)

    async def _on_follow(self: Any, event: ChannelFollowEvent) -> None:
        follow_enabled = self.app.state.features.get("follow", True)
        if not follow_enabled:
            return
        try:
            user = event.event.user_name
            broadcaster = event.event.broadcaster_user_name
            followed_at = event.event.followed_at

            message = f"{user} just followed the channel at {followed_at}!"

            self.logger.info("[_on_follow] Follow event: %s", message)

            event = TwitchFollowEvent(
                type="twitch_follow",
                data={"user": user, "followed_at": followed_at, "broadcaster": broadcaster},
                user=user,
                followed_at=followed_at,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(f"[_on_follow] Error handling follow event: {e}")

    async def _on_ready(self: Any, event: EventData) -> None:
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
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(f"[_on_ready] Failed to join channel: {e}")

    async def _on_message(self: Any, msg: ChatMessage) -> None:
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
        chat_enabled = self.app.state.features.get("chat", True)
        if not chat_enabled:
            return
        try:
            user = msg.user.name
            message = msg.text.strip()

            self.logger.debug(f"[_on_message] Message from {user}: {message}")

            source = "twitch"

            event = TwitchChatEvent(
                type="twitch_chat",
                data={"user": user, "text": message, "source": source},
                user=user,
                text=message,
                timestamp = datetime.now(timezone.utc).isoformat()
            )
            await self.event_bus.publish(event)
            self.logger.info("[_on_message] Chat message published to broker")

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error(f"[_on_message] Error handling message: {e}")
