import asyncio
from scripts.core.base_module import BaseModule
from scripts.managers.tts_manager import TTSManager 

class SpeechModule(BaseModule):
    """
    Manages text-to-speech for AI output, filtering banned words and
    speaking queued text asynchronously.

    Ignores monologue items completely.
    """

    def __init__(self, signals, speech_queue: asyncio.Queue):
        super().__init__("SpeechManager")
        self.speech_queue = speech_queue
        self.running = False
        self._consumer_task = None
        self.tts = TTSManager(signals)

    async def _consume(self):
        self.logger.info("[SpeechManager] Speech consumer started.")
        try:
            while self.running:
                item = await self.speech_queue.get()
                try:
                    text = item.get("text", "").strip()
                    item_type = item.get("type", "unknown")

                    if not text:
                        self.logger.warning("[SpeechManager] Empty text received, skipping.")
                        self.speech_queue.task_done()
                        continue

                    self.logger.info(f"[SpeechManager] Speaking ({item_type}): {text}")

                    await self.tts.speak(text)

                    if item_type != "chat_message":
                        await asyncio.sleep(3)

                except Exception as e:
                    self.logger.error(f"[SpeechManager] Error during speech playback: {e}")
                finally:
                    self.speech_queue.task_done()
        except asyncio.CancelledError:
            self.logger.info("[SpeechManager] Speech consumer cancelled.")
            raise
        except Exception as e:
            self.logger.error(f"[SpeechManager] Unexpected error in consumer: {e}")
        finally:
            self.logger.info("[SpeechManager] Speech consumer stopped.")

    async def start(self):
        """
        Starts the speech consumer task.
        """
        if not self.running:
            self.running = True
            self._consumer_task = asyncio.create_task(self._consume())
            self.logger.info("[SpeechManager] Started.")

    async def stop(self):
        """
        Stops the speech consumer task gracefully.
        """
        if self.running:
            self.running = False
            if self._consumer_task:
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass
                self._consumer_task = None
            self.logger.info("[SpeechManager] Stopped.")
        await super().stop()
