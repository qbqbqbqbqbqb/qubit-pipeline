#TODO: refactor class, too muych going on

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.output.obs_handler import OBSHandler
from src.qubit.output.tts_handler import TTSHandler
from src.qubit.core.events import ResponseGeneratedEvent
from src.qubit.output.output_sanitiser import DialogueSanitiser
from src.qubit.core.service import Service

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

    async def start(self, app) -> None:
        await super().start(app)

    async def stop(self) -> None:
        await super().stop()

    async def handle_response(self, event: ResponseGeneratedEvent) -> None:
        prompt, response, source = await self._get_event_attributes(event)

        if not response:
            self.logger.warning(f"No response generated for {prompt}")
            return

        is_valid, filtered_response = self.dialogue_sanitiser.is_valid(response)
        if not is_valid:
            self.logger.warning("[OutputHandlerService] Invalid response, skipping.")
            return

        response_clean = self.dialogue_sanitiser.strip_leading_punctuation(
            self.dialogue_sanitiser.remove_trailing_text(
            self.dialogue_sanitiser.remove_bot_name(filtered_response)))

        event = await self._set_event_attributes(event, prompt, source, response_clean)
        await self._handle_memory_event(event)
        
        await self._append_to_queue(event)

    async def _get_event_attributes(self, event) -> tuple:
        return event.prompt, event.response, event.source
    
    async def _set_event_attributes(self, event, prompt, source, response_clean) -> Any:
        event.prompt = prompt
        event.source = source
        event.response = response_clean
        return event
    
    async def _handle_memory_event(self, event) -> None:
        if self.memory_handler:
            self.memory_handler.handle_event(event)

    async def _append_to_queue(self, event) -> None:
        if event.source == "twitch_chat_processed" and event.prompt:
            pair = {
                "prompt": event.prompt,
                "response": event.response,
                "source": event.source,
                "timestamp": datetime.now(timezone.utc)
            }
            self.queue.append(pair)
        else:
            monologue = {
                "prompt": None,
                "response": event.response,
                "source": event.source,
                "timestamp": datetime.now(timezone.utc)
            }
            self.queue.append(monologue)

    async def _run(self) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue
            
            self.logger.info("Output processor started")
            while True:
                try:
                    if not self.queue:
                        await asyncio.sleep(0.05)
                        continue

                    item = self.queue.popleft()
                    self.logger.info(f"[OutputHandlerService] Processing item: {item}")

                    if await self._check_if_timestamp_stale(item):
                        continue

                    for key in ("prompt", "response"):
                        text = item.get(key)
                        if not text:
                            continue

                        await self._handle_text_output(text)

                except asyncio.CancelledError:
                    self.logger.info("Output processor cancelled")
                    break
                except Exception as e:
                    self.logger.exception(f"Error in output processor: {e}")
                    await asyncio.sleep(0.1)

    async def _check_if_timestamp_stale(self, item: dict) -> bool:
        timestamp = item.get("timestamp")
        if not timestamp:
            self.logger.warning("Item missing timestamp, skipping.")
            return True

        if datetime.now(timezone.utc) - timestamp > self.max_age:
            self.logger.info(f"Dropping stale output: {item}")
            return True
        return False
    
    async def _handle_text_output(self, text: str) -> None:
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
                self.logger.info(f"Speaking: {text}")
                await self.tts_handler.speak(text)

        finally:
            if mouth_task:
                try:
                    await mouth_task
                except Exception:
                    self.logger.exception("Mouth animation failed")

            if self.vtube_studio_handler:
                self.vtube_studio_handler.speaking = False