import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone

from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.output.obs_handler import OBSHandler
from src.qubit.output.tts_handler import TTSHandler
from src.utils.log_utils import get_logger
from src.qubit.core.event_bus import event_bus
from src.qubit.core.events import ResponseGeneratedEvent
from src.qubit.output.output_sanitiser import DialogueSanitiser
from src.qubit.core.service import Service

logger = get_logger(__name__)

class OutputHandler(Service):
    SUBSCRIPTIONS = {
        "response_generated": "handle_response"

    }
    def __init__(self, tts_handler: TTSHandler, obs_handler: OBSHandler,  vtube_studio_handler=None, max_age_seconds=30,  enable_subtitles=False, memory_handler=None):
        super().__init__("output_handler")
        self.tts_handler = tts_handler
        self.obs_handler = obs_handler
        self.vtube_studio_handler = vtube_studio_handler
        self.memory_handler = memory_handler
        self.dialogue_sanitiser = DialogueSanitiser(bot_name="Qubit", blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST)
        self.queue = deque()
        self.max_age = timedelta(seconds=max_age_seconds)
        self.enable_subtitles = enable_subtitles

        self._running = True


    async def start(self, app):
        logger.info("Starting OutputHandlerService")
        self._running = True

        self._task = asyncio.create_task(self._process_queue())
        await super().start(app)

    async def stop(self):
        logger.info("Stopping OutputHandlerService")
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def handle_response(self, event: ResponseGeneratedEvent):
        prompt = event.data.get("prompt")
        response = event.data.get("response")
        source = event.source

        if not response:
            logger.warning(f"No response generated for {prompt}")
            return

        is_valid, filtered_response = self.dialogue_sanitiser.is_valid(response)
        if not is_valid:
            logger.warning("[OutputHandlerService] Invalid response, skipping.")
            return

        response_clean = self.dialogue_sanitiser.strip_leading_punctuation(
            self.dialogue_sanitiser.remove_trailing_text(
            self.dialogue_sanitiser.remove_bot_name(filtered_response)))

        event.response = response_clean
        self.memory_handler.handle_event(event)
        
        if source == "twitch_chat_processed" and prompt:
            pair = {
                "prompt": prompt,
                "response": response_clean,
                "source": source,
                "timestamp": datetime.now(timezone.utc)
            }
            self.queue.append(pair)
        else:
            monologue = {
                "prompt": None,
                "response": response_clean,
                "source": source,
                "timestamp": datetime.now(timezone.utc)
            }
            self.queue.append(monologue)

    async def _process_queue(self):
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue
            
        logger.info("Output processor started")
        while self._running:
            try:
                if not self.queue:
                    await asyncio.sleep(0.05)
                    continue

                item = self.queue.popleft()
                logger.info(f"[OutputHandlerService] Processing item: {item}")

                timestamp = item.get("timestamp")
                if not timestamp:
                    logger.warning("Item missing timestamp, skipping.")
                    continue

                if datetime.now(timezone.utc) - timestamp > self.max_age:
                    logger.info(f"Dropping stale output: {item}")
                    continue

                for key in ("prompt", "response"):
                    text = item.get(key)
                    if not text:
                        continue

                    await self._handle_text_output(text)

            except asyncio.CancelledError:
                logger.info("Output processor cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in output processor: {e}")
                await asyncio.sleep(0.1)

    async def _handle_text_output(self, text: str):
        mouth_task = None
        try:
            if self.enable_subtitles and self.obs_handler:
                await self.obs_handler.update_subtitle_text_and_style(new_text=text)

            if self.vtube_studio_handler:
                self.vtube_studio_handler.speaking = True
                mouth_task = asyncio.create_task(
                    self.vtube_studio_handler.mouthanimation()
                )

            if self.tts_handler:
                logger.info(f"Speaking: {text}")
                await self.tts_handler.speak(text)

        finally:
            if mouth_task:
                try:
                    await mouth_task
                except Exception:
                    logger.exception("Mouth animation failed")

            if self.vtube_studio_handler:
                self.vtube_studio_handler.speaking = False