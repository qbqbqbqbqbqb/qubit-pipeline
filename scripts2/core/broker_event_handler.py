"""
Broker event handler module for managing event-driven interactions.

This module defines the BrokerEventHandler class which processes events from the central event broker,
handles input events, generates responses, and coordinates with TTS, memory, and response modules.
"""

import asyncio
import datetime
from collections import deque

from scripts2.core.central_event_broker import CentralEventBroker
from scripts2.utils.log_utils import get_logger
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from scripts2.utils.rate_limiters import TokenBucketLimiter
from scripts2.utils.message_tracker import MessageTracker

from enum import Enum

class EventType(Enum):
    """
    Enumeration of event types handled by the event broker.

    Defines the types of events that can be processed, including monologue generation,
    startup events, and Twitch chat messages.
    """
    MONOLOGUE = "monologue"
    STARTUP = "startup"
    TWITCH_CHAT = "twitch_chat"
    TWITCH_RAID = "twitch_raid"
    TWITCH_SUB = "twitch_subscription"
    TWITCH_FOLLOW = "twitch_follow"

class BrokerEventHandler:
    """
    Event handler for the central event broker.

    Processes incoming events, filters and rate-limits messages, generates responses,
    and coordinates with speech synthesis and memory modules. Handles monologue,
    startup, and Twitch chat events.
    """
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module, memory_manager):
        """
        Initializes the BrokerEventHandler with required modules.

        Args:
            broker (CentralEventBroker): The central event broker instance.
            tts_speech_module: The TTS speech module for audio output.
            response_generator_module: The module for generating responses.
            memory_manager: The memory management module.
        """
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module = response_generator_module
        self.memory_manager = memory_manager
        self._task = None
        self.logger = get_logger("BrokerEventHandler")
        self.rate_limiter = TokenBucketLimiter(rate=1.0, burst=5)
        self.message_tracker = MessageTracker()

    def start(self):
        """
        Starts the event handler task in a separate thread.
        """
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)
        self._task.add_done_callback(self._handle_task_result)

    def stop(self):
        """
        Stops the event handler task.
        """
        if self._task:
            self._task.cancel()

    def _handle_task_result(self, future):
        """
        Handles the result of the background task, logging any exceptions.

        Args:
            future: The future object from the completed task.
        """
        try:
            future.result()
        except Exception as e:
            self.logger.error(f"Background event handler task failed: {e}")

    async def _event_handler(self):
        """
        Main event handling loop that processes events from the broker.

        Subscribes to events and dispatches them to appropriate handlers.
        """
        async for event in self.broker.subscribe():
            try:
                event_type = event.get("type")
                handler = {
                    "monologue": self._handle_input_event,
                    "startup": self._handle_input_event,
                    "twitch_chat": self._handle_input_event,
                    "twitch_subscription": self._handle_input_event,
                    "twitch_raid": self._handle_input_event,
                    "twitch_follow": self._handle_input_event,
                    "response_prompt": self._handle_response_prompt,
                    "response_generated": self._handle_response_generated,
                    "memories_updated": self._handle_memories_updated,
                }.get(event_type)

                if handler:
                    await handler(event)
                else:
                    self.logger.debug(f"Ignoring unknown event type: {event_type}")

            except Exception as e:
                self.logger.error(f"Error processing event {event}: {e}")

    async def _handle_input_event(self, event):
        """
        Handles input events such as monologue, startup, and Twitch chat.

        Filters, rate-limits, and processes messages before publishing response prompts.

        Args:
            event (dict): The event data containing type, user, text, etc.
        """
        self.message_tracker.cleanup()
        event_type = event.get("type")
        user = event.get("user", "Someone")

        text = event.get("text", "")
        if event_type == EventType.TWITCH_CHAT.value:
            if contains_banned_words(text, blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST):
                return
    
            if contains_banned_words(user, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST):
                user = "Someone"

            if self._should_ignore_message(text) or self.message_tracker.is_repeated(text):
                self._log_and_store_ignored_message(text, user, event_type)
                return
            
            if self.message_tracker.is_responded(text):
                self.logger.debug(f"Skipping previously responded message: '{text}'")
                return

            self.message_tracker.add_message(text)

            if not self.rate_limiter.allow():
                self.logger.debug(f"Rate limited message: '{text}'")
                return
            
        if (event_type == EventType.TWITCH_FOLLOW.value or 
            event_type == EventType.TWITCH_RAID.value or 
            event_type == EventType.TWITCH_SUB.value):
                if contains_banned_words(user, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST):
                    user = "Someone"

        self._publish_response_prompt(event_type, user, text)

    async def _handle_response_generated(self, event):
        """
        Handles generated response events by saving to memory and submitting to TTS.

        Args:
            event (dict): The response event data.
        """
        prompt = event.get("original_prompt", "")
        self.message_tracker.cleanup()

        user = event.get("original_full", {}).get("user", "Someone")
        original_type = event.get("original_type", "")
        response_text = event.get("response", "")

        self.logger.debug(f"Responding to {user}: '{prompt}' → '{response_text}'")

        if self.memory_manager:
            self.memory_manager.save_conversation_turn(
                assistant_content=response_text,
                assistant_metadata={"type": event["type"], "original_type": original_type}
            )

        source = event.get("original_full", {}).get("original_type") or event.get("source") or ""
        try:
            if source == EventType.TWITCH_CHAT.value:
                self.tts_speech_module.submit_pair({
                    "user_text": f"{user} said: {prompt}",
                    "response_text": response_text
                })
            else:
                self.tts_speech_module.submit_monologue({"text": response_text})
        except Exception as e:
            self.logger.error(f"TTS submission failed: {e}")

        self.message_tracker.add_responded(prompt)

    async def _handle_response_prompt(self, event):
        """
        Handles response prompt events by submitting them to the response generator with priority.

        Args:
            event (dict): The prompt event data.
        """
        if self._is_stale_monologue(event):
            return

        original_type = event.get("original_type")
        if original_type == EventType.STARTUP.value:
            priority = 1 
        elif (original_type == EventType.TWITCH_FOLLOW.value or 
                original_type == EventType.TWITCH_RAID.value or 
                original_type == EventType.TWITCH_SUB.value):
            priority = 3
        else:
            priority = 5
        
        self.response_generator_module.submit_prompt(event, priority)

    async def _handle_memories_updated(self, event):
        """
        Handles memory update events by notifying the prompt manager.

        Args:
            event (dict): The memory update event data.
        """
        handler = getattr(self.response_generator_module.prompt_manager, "handle_memory_update", None)
        if handler:
            handler(event.get("data"))

    # === Helpers ===

    def _should_ignore_message(self, message: str) -> bool:
        """
        Determines if a message should be ignored based on length.

        Args:
            message (str): The message text.

        Returns:
            bool: True if the message should be ignored.
        """
        return len(message.strip().split()) < 2

    def _log_and_store_ignored_message(self, text: str, user: str, source: str):
        """
        Logs and stores ignored messages in memory.

        Args:
            text (str): The message text.
            user (str): The user who sent the message.
            source (str): The source of the message.
        """
        reason = "short" if self._should_ignore_message(text) else "repeated"
        self.logger.debug(f"Skipping {reason} twitch_chat message: '{text}'")
        if self.memory_manager:
            self.memory_manager.add_conversation_item(
                role="user",
                content=text,
                user_id=user,
                metadata={"type": "ignored_message", "reason": f"failed_{reason}", "source": source}
            )

    def _is_stale_monologue(self, event) -> bool:
        """
        Checks if a monologue event is stale (older than 5 seconds).

        Args:
            event (dict): The monologue event.

        Returns:
            bool: True if the monologue is stale.
        """
        if event.get("original_type") != EventType.MONOLOGUE.value:
            return False

        ts_str = event.get("timestamp")
        if not ts_str:
            return False

        try:
            event_time = datetime.datetime.fromisoformat(ts_str)
        except ValueError:
            self.logger.warning(f"Invalid timestamp format in event: {ts_str}")
            return True
        age = (datetime.datetime.now(datetime.timezone.utc) - event_time).total_seconds()
        if age > 5:
            self.logger.debug(f"Skipping stale monologue (age {age:.1f}s): '{event.get('text', '')}'")
            return True
        return False

    def _publish_response_prompt(self, event_type: str, user: str, text: str):
        """
        Publishes a response prompt event to the broker.

        Args:
            event_type (str): The type of the original event.
            user (str): The user associated with the event.
            text (str): The text content.
        """
        event = {
            "type": "response_prompt",
            "source": event_type,
            "user": user,
            "text": text,
            "original_type": event_type,
        }
        if event_type == EventType.MONOLOGUE.value:
            event["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.broker.publish_event(event)
