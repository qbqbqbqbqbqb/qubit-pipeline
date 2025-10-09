import asyncio

from scripts2.core.central_event_broker import CentralEventBroker
from scripts2.utils.log_utils import get_logger
from scripts2.utils.filter_utils import contains_banned_words
from scripts2.config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST

class BrokerEventHandler:
    def __init__(self, broker: CentralEventBroker, tts_speech_module, response_generator_module, memory_manager):
        self.broker = broker
        self.tts_speech_module = tts_speech_module
        self.response_generator_module=response_generator_module
        self._task = None
        self.memory_manager = memory_manager
        self.logger = get_logger("BrokerEventHandler")

    def start(self):
        self._task = asyncio.run_coroutine_threadsafe(self._event_handler(), self.broker.loop)

    async def _event_handler(self):
        async for event in self.broker.subscribe():
            event_type = event.get("type")
            try:
                if event_type in ("twitch_chat"):
                    user = event.get("user", "someone")
                    if contains_banned_words(text=user, blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST):
                        user = "Someone"
                    
                if event_type in ("monologue", "startup"):
                    user = "system"

                    self.broker.publish_event({
                        "type": "response_prompt",
                        "source": event_type,
                        "user": user,
                        "text": event.get("text"),
                        "original_type": event_type
                    })

                elif event["type"] == "response_generated":
                    original_type = event.get("original_type", "")
                    original_full = event.get("original_full", {})
                    user = original_full.get("user", "Someone")
                    original_prompt = event.get("original_prompt", "")
                    response_text = event.get("response", "")
                    
                                
                    if self.memory_manager:
                        self.memory_manager.save_conversation_turn(
                            assistant_content=response_text,
                            assistant_metadata={"type": event["type"],
                                                "original_type": original_type}
                        )

                    #self.logger.debug(event)
                    #self.logger.info(f"Original type in response_generated event: '{original_type}'")

                    source_type = original_full.get("original_type") or original_full.get("source") or ""

                    if source_type == "startup":
                        priority = 1
                    else:
                        priority = 10
                    
                    if source_type == "twitch_chat":
                        chat_msg = f"{user} said: {original_prompt}"
                        original_chat_event = {
                            "type": "chat_response_input",
                            "response": chat_msg,
                            "original_prompt": original_prompt,
                            "original_type": "twitch_chat",
                            "original_full": original_full,
                        }
                        self.tts_speech_module.submit_response(original_chat_event, priority - 1)
                        self.logger.debug(f"[BrokerEventHandler] Queued user message for TTS: '{chat_msg}' with priority {priority - 1}")

                    self.tts_speech_module.submit_response(event, priority)
                    self.logger.debug(f"[BrokerEventHandler] Queued bot response for TTS: '{event.get('response')}' with priority {priority}")

                elif event["type"] == "response_prompt":
                    text = event.get("text", "")
                    if contains_banned_words(text=text, blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST):
                        self.logger.info(f"Dropping prompt due to banned words in text: '{text}'")
                        continue
                    
                    if event["original_type"] == "startup":
                        priority = 1
                    else:
                        priority = 10
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
