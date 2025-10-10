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
    MONOLOGUE = "monologue"
    STARTUP = "startup"
    TWITCH_CHAT = "twitch_chat"

class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module, memory_manager):
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module = response_generator_module
        self.memory_manager = memory_manager
        self._task = None
        self.logger = get_logger("BrokerEventHandler")
        self.rate_limiter = TokenBucketLimiter(rate=1.0, burst=5)
        self.message_tracker = MessageTracker()

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)
        self._task.add_done_callback(self._handle_task_result)

    def stop(self):
        if self._task:
            self._task.cancel()

    def _handle_task_result(self, future):
        try:
            future.result()
        except Exception as e:
            self.logger.error(f"Background event handler task failed: {e}")

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            try:
                event_type = event.get("type")
                handler = {
                    "monologue": self._handle_input_event,
                    "startup": self._handle_input_event,
                    "twitch_chat": self._handle_input_event,
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
        self.message_tracker.cleanup()
        event_type = event.get("type")
        user = event.get("user", "someone")

        text = event.get("text", "")
        if event_type == EventType.TWITCH_CHAT.value:
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

        self._publish_response_prompt(event_type, user, text)

    async def _handle_response_generated(self, event):
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
        if self._is_stale_monologue(event):
            return

        priority = 1 if event.get("original_type") == EventType.STARTUP.value else 5
        self.response_generator_module.submit_prompt(event, priority)

    async def _handle_memories_updated(self, event):
        handler = getattr(self.response_generator_module.prompt_manager, "handle_memory_update", None)
        if handler:
            handler(event.get("data"))

    # === Helpers ===

    def _should_ignore_message(self, message: str) -> bool:
        return len(message.strip().split()) < 2

    def _log_and_store_ignored_message(self, text: str, user: str, source: str):
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
