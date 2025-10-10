import asyncio
import datetime
from collections import deque

from scripts2.core.central_event_broker import CentralEventBroker
from scripts2.utils.log_utils import get_logger
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST


class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module, memory_manager):
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module = response_generator_module
        self.memory_manager = memory_manager
        self.recent_messages = deque(maxlen=100)
        self._task = None
        self.logger = get_logger("BrokerEventHandler")

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            try:
                handler = {
                    "monologue": self._handle_input_event,
                    "startup": self._handle_input_event,
                    "twitch_chat": self._handle_input_event,
                    "response_prompt": self._handle_response_prompt,
                    "response_generated": self._handle_response_generated,
                    "memories_updated": self._handle_memories_updated,
                }.get(event.get("type"))

                if handler:
                    await handler(event)
                else:
                    self.logger.debug(f"Ignoring unknown event type: {event.get('type')}")

            except Exception as e:
                self.logger.error(f"Error processing event {event}: {e}")

    async def _handle_input_event(self, event):
        event_type = event.get("type")
        text = event.get("text", "")
        user = event.get("user", "system") if event_type != "twitch_chat" else event.get("user", "someone")

        if event_type == "twitch_chat":
            if contains_banned_words(user, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST):
                user = "Someone"

            if self._should_ignore_message(text) or self._is_repeated_recently(text):
                self._log_and_store_ignored_message(text, user, event_type)
                return

            self._add_recent_message(text)
            if self._is_message_overwhelmed(text):
                return

        self._publish_response_prompt(event_type, user, text)

    async def _handle_response_generated(self, event):
        user = event.get("original_full", {}).get("user", "Someone")
        original_type = event.get("original_type", "")
        original_prompt = event.get("original_prompt", "")
        response_text = event.get("response", "")

        self.logger.debug(f"Responding to {user}: '{original_prompt}' → '{response_text}'")

        if self.memory_manager:
            self.memory_manager.save_conversation_turn(
                assistant_content=response_text,
                assistant_metadata={"type": event["type"], "original_type": original_type}
            )

        source = event.get("original_full", {}).get("original_type") or event.get("source") or ""
        if source == "twitch_chat":
            pair = {"user_text": f"{user} said: {original_prompt}", "response_text": response_text}
            self.tts_speech_module.submit_pair(pair)
        else:
            self.tts_speech_module.submit_monologue({"text": response_text})

    async def _handle_response_prompt(self, event):
        if self._is_stale_monologue(event):
            return

        priority = 1 if event.get("original_type") == "startup" else 5
        self.response_generator_module.submit_prompt(event, priority)

    async def _handle_memories_updated(self, event):
        handler = getattr(self.response_generator_module.prompt_manager, "handle_memory_update", None)
        if handler:
            handler(event.get("data"))

    # ----------------- Helpers ------------------

    def _should_ignore_message(self, message: str) -> bool:
        return len(message.strip().split()) < 2

    def _is_repeated_recently(self, msg_text: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        return any(msg_text == text and (now - ts).total_seconds() < 60 for text, ts in self.recent_messages)

    def _add_recent_message(self, msg_text: str):
        self.recent_messages.append((msg_text, datetime.datetime.now(datetime.timezone.utc)))

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

    def _is_message_overwhelmed(self, text: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        chat_speed = sum((now - ts).total_seconds() <= 10 for _, ts in self.recent_messages)
        if chat_speed <= 10:
            return False

        scored = [(self._score_message(t, ts), t) for t, ts in self.recent_messages if (now - ts).total_seconds() <= 60]
        scored.sort(reverse=True)
        top_message = scored[0][1] if scored else None
        return top_message != text

    def _score_message(self, message_text, timestamp, half_life_seconds=60):
        age = (datetime.datetime.now(datetime.timezone.utc) - timestamp).total_seconds()
        decay = 0.5 ** (age / half_life_seconds)
        return len(message_text) * decay

    def _is_stale_monologue(self, event) -> bool:
        if event.get("original_type") != "monologue":
            return False

        ts_str = event.get("timestamp")
        if not ts_str:
            return False

        event_time = datetime.datetime.fromisoformat(ts_str)
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
        if event_type == "monologue":
            event["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.broker.publish_event(event)
