import asyncio
from scripts.bot.bot_utils import contains_banned_words, filter_banned_words
from scripts.io.tts_utils import speak_from_prompt

from scripts.utils.log_utils import get_logger
logger = get_logger("SpeechManager")

class SpeechManager:
    """
    Manages text-to-speech conversion and audio playback for the VTuber bot.

    Processes queued speech items, performs content filtering for banned words,
    and handles monologue pause/resume functionality. Integrates with TTS
    system to convert text to spoken audio output.
    """

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
            logger.debug(f"[SpeechManager] Dequeued item: {item}")

            try:
                text = item.get("text", "").strip()
                item_type = item.get("type", "unknown")

                if not text:
                    logger.warning("[SpeechManager] Empty text received, skipping.")
                    self.speech_queue.task_done()
                    continue
               
                if contains_banned_words(text, banned_words=self.banned_words):
                    text = filter_banned_words(text, banned_words=self.banned_words)
                    logger.warning(f"[SpeechManager] Filtered banned words in text: {text}")
                
                if item["type"] == "monologue":
                    if not self.monologue_running:
                        logger.debug("[SpeechManager] Monologue paused, skipping speech.")
                        continue
                    logger.info(f"[SpeechManager] Speaking monologue: {text}")
                elif item_type in ["follow_response", "sub_response", "raid_response"]:
                    logger.info(f"[SpeechManager] Speaking event response ({item_type}): {text}")
                else:
                    logger.info(f"[SpeechManager] Speaking ({item_type}): {text}")

                await speak_from_prompt(text)

                if item_type != "chat_message":
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error during speech playback: {e}")
            finally:
                self.speech_queue.task_done()

    def pause_monologues(self):
        self.monologue_running = False
        logger.info("[SpeechManager] Monologue paused.")

    def resume_monologues(self):
        self.monologue_running = True
        logger.info("[SpeechManager] Monologue resumed.")
