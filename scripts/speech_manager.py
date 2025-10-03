import asyncio
from bot_utils import contains_banned_words
from tts_utils import speak_from_prompt

from log_utils import get_logger
logger = get_logger("SpeechManager")

class SpeechManager:
    def __init__(self, speech_queue, banned_words):
        self.speech_queue = speech_queue
        self.banned_words = banned_words
        self.monologue_running = True

    async def consume(self):
        """
        Consume the speech queue and perform TTS on queued items.
        Skips monologue speech if paused.
        """
        while True:
            item = await self.speech_queue.get()
            try:
                if item["type"] == "monologue" and not self.monologue_running:
                    logger.debug("[SpeechManager] Monologue paused, skipping speech.")
                else:
                    text = item["text"]
                    if contains_banned_words(text, banned_words=self.banned_words):
                        logger.warning(f"[SpeechManager] Blocked TTS due to banned content: {text}")
                        continue
                    await speak_from_prompt(text)

                    if(["type"] != "chat_response"):
                        await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error during speech playback: {e}")
            finally:
                self.speech_queue.task_done()
