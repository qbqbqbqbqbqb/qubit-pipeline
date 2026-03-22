"""Output handler service for TTS, OBS subtitles, and VTuber integration.

This module provides OutputHandler, a service that processes generated
responses, sanitizes dialogue, handles TTS playback, updates OBS subtitles,
and optionally interacts with VTuber Studio for mouth animation. It
supports asynchronous operation using asyncio and maintains a queue of
recent outputs, with automatic removal of stale items.

Classes:
    OutputHandler: Main service handling the output pipeline.
"""
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
    """Service for processing generated responses to TTS, subtitles, and VTuber output.

    Handles dialogue sanitisation, memory integration, OBS subtitle updates,
    TTS synthesis, and optional VTuber mouth animations. Maintains an
    asynchronous queue of recent outputs and drops stale items.

    Attributes:
        tts_handler (TTSHandler): TTS engine for speaking text.
        obs_handler (OBSHandler): OBS handler for updating subtitles.
        vtube_studio_handler (Optional[Any]): Optional VTuber Studio integration.
        memory_handler (Optional[Any]): Optional memory handler for events.
        dialogue_sanitiser (DialogueSanitiser): Sanitiser for filtering responses.
        queue (deque): Queue of recent outputs.
        max_age (timedelta): Maximum age for outputs before dropping.
        enable_subtitles (bool): Whether to update OBS subtitles.
    """

    SUBSCRIPTIONS = {
        "response_generated": "handle_response"

    }

    def __init__(self: Any, tts_handler: TTSHandler, obs_handler: OBSHandler,  vtube_studio_handler=None, max_age_seconds:int=30,  enable_subtitles:bool=False, memory_handler=None):
        """Initialise the OutputHandler service.

        Args:
            tts_handler (TTSHandler): TTS engine for speaking text.
            obs_handler (OBSHandler): OBS handler for updating subtitles.
            vtube_studio_handler (Optional[Any]): VTuber Studio mouth animation handler.
            max_age_seconds (int): Maximum age of queued items before dropping.
            enable_subtitles (bool): Whether to enable OBS subtitles.
            memory_handler (Optional[Any]): Optional memory handler for events.
        """
        super().__init__("output_handler")
        self.tts_handler = tts_handler
        self.obs_handler = obs_handler
        self.vtube_studio_handler = vtube_studio_handler
        self.memory_handler = memory_handler
        self.dialogue_sanitiser = DialogueSanitiser(blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST)
        self.queue = deque()
        self.max_age = timedelta(seconds=max_age_seconds)
        self.enable_subtitles = enable_subtitles

    async def start(self: Any, app: Any) -> None:
        """Start the output handler service.

        Args:
            app (Any): Reference to the application instance.
        """
        await super().start(app)

    async def stop(self: Any) -> None:
        """Stop the output handler service."""
        await super().stop()

    async def handle_response(self: Any, event: ResponseGeneratedEvent) -> None:
        """Process a generated response event.

        This includes sanitising dialogue, checking validity, updating memory,
        and appending the event to the output queue.

        Args:
            event (ResponseGeneratedEvent): Event containing the generated response.
        """
        prompt, response, source = await self._get_event_attributes(event)

        if not response:
            self.logger.warning("[handle_response] No response generated for %s", prompt)
            return

        is_valid, filtered_response = self.dialogue_sanitiser.is_valid(response)
        if not is_valid:
            self.logger.warning("[handle_response] Invalid response, skipping.")
            return

        response_clean = self.dialogue_sanitiser.strip_leading_punctuation(
            self.dialogue_sanitiser.remove_trailing_text(
            self.dialogue_sanitiser.remove_bot_name(filtered_response)))

        event = await self._set_event_attributes(event, prompt, source, response_clean)
        await self._handle_memory_event(event)

        await self._append_to_queue(event)

    async def _get_event_attributes(self: Any, event: ResponseGeneratedEvent) -> tuple:
        """Retrieve key attributes from a response event.

        Args:
            event (ResponseGeneratedEvent): Event to extract attributes from.

        Returns:
            tuple: (prompt, response, source)
        """
        return event.prompt, event.response, event.source

    async def _set_event_attributes(self: Any, event: ResponseGeneratedEvent, prompt: str, source: str, response_clean: str) -> Any:
        """Update event attributes after sanitisation.

        Args:
            event (ResponseGeneratedEvent): Event to update.
            prompt (str): Original prompt.
            source (str): Source of the response.
            response_clean (str): Sanitised response text.

        Returns:
            ResponseGeneratedEvent: Updated event.
        """
        event.prompt = prompt
        event.source = source
        event.response = response_clean
        return event

    async def _handle_memory_event(self: Any, event: ResponseGeneratedEvent) -> None:
        """Forward the event to memory handler if available.

        Args:
            event (ResponseGeneratedEvent): Event to store in memory.
        """
        if self.memory_handler:
            self.memory_handler.handle_event(event)

    async def _append_to_queue(self: Any, event: ResponseGeneratedEvent) -> None:
        """Append a response event to the output queue with timestamp.

        Args:
            event (ResponseGeneratedEvent): Event to append.
        """
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

    async def _run(self: Any) -> None:
        """Main loop processing the output queue asynchronously."""
        await super()._run()
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            self.logger.info("[_run] Output processor started")
            while True:
                try:
                    if not self.queue:
                        await asyncio.sleep(0.05)
                        continue

                    item = self.queue.popleft()
                    self.logger.info("[_run] Processing item: %s", item)

                    if await self._check_if_timestamp_stale(item):
                        continue

                    for key in ("prompt", "response"):
                        text = item.get(key)
                        if not text:
                            continue

                        await self._handle_text_output(text)

                except asyncio.CancelledError:
                    self.logger.info("[_run] Output processor cancelled")
                    break
                except Exception as e:
                    self.logger.exception("[_run] Error in output processor: %s", e)
                    await asyncio.sleep(0.1)


    async def _check_if_timestamp_stale(self: Any, item: dict) -> bool:
        """Check if the queued item is too old and should be dropped.

        Args:
            item (dict): Queued output item with timestamp.

        Returns:
            bool: True if the item is stale and should be ignored.
        """
        timestamp = item.get("timestamp")
        if not timestamp:
            self.logger.warning("[_check_if_timestamp_stale] Item missing timestamp, skipping.")
            return True

        if datetime.now(timezone.utc) - timestamp > self.max_age:
            self.logger.info("[_check_if_timestamp_stale] Dropping stale output: %s", item)
            return True
        return False


    async def _handle_text_output(self: Any, text: str) -> None:
        """Process a single text output: TTS, subtitles, VTuber mouth animation.

        Args:
            text (str): Text to process for output.
        """
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
                self.logger.info("[_handle_text_output] Speaking: %s", text)
                await self.tts_handler.speak(text)

        finally:
            if mouth_task:
                try:
                    await mouth_task
                except Exception:
                    self.logger.exception("[_handle_text_output] Mouth animation failed")

            if self.vtube_studio_handler:
                self.vtube_studio_handler.speaking = False
