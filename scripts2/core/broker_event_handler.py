import asyncio
from collections import deque
import datetime

from scripts2.core.central_event_broker import CentralEventBroker
from scripts2.utils.log_utils import get_logger
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST

class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module, memory_manager):
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module = response_generator_module
        self._task = None
        self.memory_manager = memory_manager
        self.logger = get_logger("BrokerEventHandler")
        self.recent_messages = deque(maxlen=100)

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)


    def _get_chat_speed(self, interval_seconds=10):
        now = datetime.datetime.now(datetime.timezone.utc)
        count = 0
        for _, timestamp in self.recent_messages:
            if (now - timestamp).total_seconds() <= interval_seconds:
                count += 1
        return count

    def _decay_weight(self, timestamp, half_life_seconds=60):
        now = datetime.datetime.now(datetime.timezone.utc)
        age = (now - timestamp).total_seconds()
        weight = 0.5 ** (age / half_life_seconds)
        return weight
    
    def _score_message(self, message_text, timestamp):
        base_score = len(message_text) 
        decay = self._decay_weight(timestamp)
        return base_score * decay

    def _should_ignore_message(self, message: str) -> bool:
        words = message.strip().split()
        return len(words) < 2

    def _is_repeated_recently(self, msg_text: str) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        for text, timestamp in self.recent_messages:
            if msg_text == text and (now - timestamp).total_seconds() < 60:
                return True
        return False

    def _add_recent_message(self, msg_text: str):
        self.recent_messages.append((msg_text, datetime.datetime.now(datetime.timezone.utc)))

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            event_type = event.get("type")
            try:
                if event_type in ("monologue", "startup", "twitch_chat"):
                    text = event.get("text", "")

                    if event_type == "twitch_chat":
                        user = event.get("user", "someone")

                        if contains_banned_words(text=user, blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST):
                            user = "Someone"

                        if self._should_ignore_message(text) or self._is_repeated_recently(text):
                            if self._should_ignore_message(text):
                                self.logger.debug(f"Skipping short/ignored twitch_chat message: '{text}'")
                            else:
                                self.logger.debug(f"Skipping repeated twitch_chat message for response generation: '{text}'")
                            if self.memory_manager:
                                self.memory_manager.add_conversation_item(
                                    role="user",
                                    content=text,
                                    user_id=user,
                                    metadata={"type": "ignored_message", "reason": "failed_filter", "source": event_type}
                                )
                            continue


                        self._add_recent_message(text)
                        chat_speed = self._get_chat_speed()

                        scored_messages = []
                        now = datetime.datetime.now(datetime.timezone.utc)
                        for msg_text, timestamp in self.recent_messages:
                            if (now - timestamp).total_seconds() <= 60:
                                score = self._score_message(msg_text, timestamp)
                                scored_messages.append((score, msg_text))

                        scored_messages.sort(reverse=True, key=lambda x: x[0])

                        if chat_speed > 10:
                            top_message = scored_messages[0][1] if scored_messages else None
                            if top_message and top_message != text:
                                continue

                    if event_type in ("monologue", "startup"):
                        user = "system"

                    self.broker.publish_event({
                        "type": "response_prompt",
                        "source": event_type,
                        "user": user,
                        "text": text,
                        "original_type": event_type,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    })

                elif event["type"] == "response_generated":
                    original_type = event.get("original_type", "")
                    original_full = event.get("original_full", {})
                    user = original_full.get("user", "Someone")
                    original_prompt = event.get("original_prompt", "")
                    response_text = event.get("response", "")

                    self.logger.debug(f"Responding to chat message from {user}: '{original_prompt}' with: '{response_text}'")

                    if self.memory_manager:
                        self.memory_manager.save_conversation_turn(
                            assistant_content=response_text,
                            assistant_metadata={"type": event["type"], "original_type": original_type}
                        )

                    source_type = original_full.get("original_type") or original_full.get("source") or ""

                    if source_type == "twitch_chat":
                        chat_msg = f"{user} said: {original_prompt}"
                        pair = {"user_text": chat_msg, "response_text": response_text}
                        self.tts_speech_module.submit_pair(pair)
                        self.logger.debug(f"[BrokerEventHandler] Submitted pair for TTS: user '{chat_msg}', response '{response_text}'")
                    else:
                        monologue = {"text": response_text}
                        self.tts_speech_module.submit_monologue(monologue)
                        self.logger.debug(f"[BrokerEventHandler] Submitted monologue for TTS: '{response_text}'")

                elif event["type"] == "response_prompt":
                    text = event.get("text", "")

                    if event.get("original_type") == "monologue":
                        timestamp_str = event.get("timestamp")
                        if timestamp_str:
                            event_time = datetime.datetime.fromisoformat(timestamp_str)
                            now = datetime.datetime.now(datetime.timezone.utc)
                            age_seconds = (now - event_time).total_seconds()

                            if age_seconds > 5:
                                self.logger.debug(f"Skipping stale monologue (age {age_seconds:.1f}s): '{text}'")
                                continue

                    priority = 1 if event["original_type"] == "startup" else 5
                    self.response_generator_module.submit_prompt(event, priority)

                elif event["type"] == "memories_updated":
                    if self.response_generator_module and hasattr(self.response_generator_module.prompt_manager, "handle_memory_update"):
                        self.response_generator_module.prompt_manager.handle_memory_update(event["data"])

                else:
                    pass

            except Exception as e:
                print(f"Error processing event {event}: {e}")

    def stop(self):
        if self._task:
            self._task.cancel()
