"""
<summary>
OutputCoordinator — central coordinator for the entire output pipeline.
</summary>
<remarks>
LAYER: Output

Owns the split output queue, staleness logic, and drives ai_speaking state on RuntimeState.
Delegates actual implementation to leaf handlers: TTSHandler, OBSHandler, VTubeStudioHandler,
PNGOutputHandler, and DialogueSanitiser.

Two deques are maintained instead of one: priority_queue for community-event reactions
(raids/gifts/follows), queue for everything else. The priority queue is always drained
first and gets a longer staleness allowance (priority_max_age) because community events
are rare and should not be dropped behind a chat backlog.

Both deques are capped (maxlen) to bound memory growth if output stalls.
Detection of a community-event response reads event.data['kind'] == 'community_event',
set by DecisionExecutor when constructing the originating MonologueEvent. Events without
this key fall back to normal-priority handling silently.
</remarks>
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from config.config import BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST
from src.qubit.output.handlers.png import PNGOutputHandler
from src.qubit.output.handlers.obs import OBSHandler
from src.qubit.output.handlers.tts import TTSHandler
from src.qubit.output.handlers.sanitiser import DialogueSanitiser
from src.qubit.core.events import ResponseGeneratedEvent
from src.qubit.core.service import Service


class OutputCoordinator(Service):
    """
    <summary>
    Service that owns the response queues and coordinates all output handlers.
    The single place that sets and clears ai_speaking on RuntimeState.
    </summary>
    """

    SUBSCRIPTIONS = {
        "response_generated": "handle_response"
    }

    DEFAULT_QUEUE_MAXLEN = 40
    DEFAULT_PRIORITY_QUEUE_MAXLEN = 20
    DEFAULT_PRIORITY_MAX_AGE_SECONDS = 120

    def __init__(
        self: Any,
        tts_handler: TTSHandler,
        obs_handler: OBSHandler,
        vtube_studio_handler=None,
        max_age_seconds: int = 30,
        priority_max_age_seconds: int = DEFAULT_PRIORITY_MAX_AGE_SECONDS,
        queue_maxlen: int = DEFAULT_QUEUE_MAXLEN,
        priority_queue_maxlen: int = DEFAULT_PRIORITY_QUEUE_MAXLEN,
        enable_subtitles: bool = False,
    ):
        """
        <summary>Initialise the coordinator with output handlers and queue settings.</summary>
        <param name="tts_handler">The TTS leaf handler.</param>
        <param name="obs_handler">The OBS subtitle leaf handler.</param>
        <param name="vtube_studio_handler">Optional VTube Studio animation handler.</param>
        <param name="max_age_seconds">Staleness window for normal-priority queue items.</param>
        <param name="priority_max_age_seconds">Staleness window for priority queue items (community events).</param>
        <param name="queue_maxlen">Maximum capacity of the normal-priority deque.</param>
        <param name="priority_queue_maxlen">Maximum capacity of the community-event deque.</param>
        <param name="enable_subtitles">When True, OBSHandler is called to update subtitles before each TTS call.</param>
        """
        super().__init__("output_coordinator")
        self.tts_handler = tts_handler
        self.obs_handler = obs_handler
        self.vtube_studio_handler = vtube_studio_handler
        self.png_handler: PNGOutputHandler = None
        self.dialogue_sanitiser = DialogueSanitiser(
            blacklist=BLACKLISTED_WORDS_LIST,
            whitelist=WHITELISTED_WORDS_LIST,
        )

        self.queue: deque = deque(maxlen=queue_maxlen)
        self.priority_queue: deque = deque(maxlen=priority_queue_maxlen)

        self.max_age = timedelta(seconds=max_age_seconds)
        self.priority_max_age = timedelta(seconds=priority_max_age_seconds)
        self.enable_subtitles = enable_subtitles

    def attach(self, app) -> None:
        """
        <summary>Bind to the app. VTube Studio connection is deferred to _run().</summary>
        <param name="app">The root App instance.</param>
        """
        super().attach(app)

    async def stop(self: Any) -> None:
        """<summary>Stop the output coordinator service.</summary>"""
        await super().stop()

    async def handle_response(self: Any, event: ResponseGeneratedEvent) -> None:
        """
        <summary>
        Sanitise a generated response and append it to the appropriate output queue.
        Drops the event if the response is empty or fails the banned-word check.
        </summary>
        <param name="event">The ResponseGeneratedEvent to process.</param>
        """
        prompt, response, source = self._get_event_attributes(event)

        if not response:
            self.logger.warning("[handle_response] No response for prompt: %s", prompt)
            return

        is_valid, filtered_response = self.dialogue_sanitiser.is_valid(response)
        if not is_valid:
            self.logger.warning("[handle_response] Invalid response, skipping.")
            return

        def _log_mutation(step: str, before: str, after: str):
            if after != before:
                self.logger.info("[handle_response] %s changed text: %r -> %r", step, before, after)

        after_bot = self.dialogue_sanitiser.remove_bot_name(filtered_response)
        _log_mutation("remove_bot_name", filtered_response, after_bot)

        after_trailing = self.dialogue_sanitiser.remove_trailing_text(after_bot)
        _log_mutation("remove_trailing_text", after_bot, after_trailing)

        response_clean = self.dialogue_sanitiser.strip_leading_punctuation(after_trailing)
        _log_mutation("strip_leading_punctuation", after_trailing, response_clean)

        event = self._set_event_attributes(event, prompt, source, response_clean)
        await self._handle_memory_event(event)
        await self._append_to_queue(event)

    def _get_event_attributes(self: Any, event: ResponseGeneratedEvent) -> tuple:
        """
        <summary>Extract prompt, response, and source from a ResponseGeneratedEvent.</summary>
        <param name="event">The event to extract from.</param>
        <returns>A (prompt, response, source) tuple.</returns>
        """
        return event.prompt, event.response, event.source

    def _set_event_attributes(
        self: Any, event: ResponseGeneratedEvent, prompt: str, source: str, response_clean: str
    ) -> Any:
        """
        <summary>Write sanitised values back onto the event in place.</summary>
        <param name="event">The event to update.</param>
        <param name="prompt">The original prompt.</param>
        <param name="source">The response source string.</param>
        <param name="response_clean">The sanitised response text.</param>
        <returns>The updated event.</returns>
        """
        event.prompt = prompt
        event.source = source
        event.response = response_clean
        return event

    async def _handle_memory_event(self: Any, event: ResponseGeneratedEvent) -> None:
        """
        <summary>Forward the sanitised event to a memory writer if one is available.</summary>
        <param name="event">The sanitised ResponseGeneratedEvent.</param>
        """

    def _is_priority_event(self: Any, event: ResponseGeneratedEvent) -> bool:
        """
        <summary>
        Return True if this event is a community-event reaction (raid, gift, follow).
        Reads event.data['kind'] == 'community_event', written by DecisionExecutor.
        Falls back silently to False if the field is absent.
        </summary>
        <param name="event">The ResponseGeneratedEvent to inspect.</param>
        <returns>True if the event is a community-event reaction.</returns>
        """
        data = getattr(event, "data", None) or {}
        return data.get("kind") == "community_event"

    async def _append_to_queue(self: Any, event: ResponseGeneratedEvent) -> None:
        """
        <summary>
        Append the sanitised event to the priority or normal queue, timestamped now.
        The deque's maxlen evicts the oldest item automatically when full.
        </summary>
        <param name="event">The event to enqueue.</param>
        """
        is_priority = self._is_priority_event(event)
        target_queue = self.priority_queue if is_priority else self.queue

        if event.source in ("twitch_chat_filtered", "kick_chat_filtered") and event.prompt:
            item = {
                "prompt": event.prompt,
                "response": event.response,
                "source": event.source,
                "timestamp": datetime.now(timezone.utc),
                "priority": is_priority,
            }
        else:
            item = {
                "prompt": None,
                "response": event.response,
                "source": event.source,
                "timestamp": datetime.now(timezone.utc),
                "priority": is_priority,
            }

        target_queue.append(item)

    def _pop_next_item(self: Any) -> tuple:
        """
        <summary>Pop the next item, draining the priority queue first.</summary>
        <returns>A (item, from_priority) tuple, or (None, False) if both queues are empty.</returns>
        """
        if self.priority_queue:
            return self.priority_queue.popleft(), True
        if self.queue:
            return self.queue.popleft(), False
        return None, False

    def _requeue_front(self: Any, item: dict, from_priority: bool) -> None:
        """
        <summary>Push an item back to the front of the queue it came from.</summary>
        <param name="item">The item to requeue.</param>
        <param name="from_priority">True if the item came from the priority queue.</param>
        """
        (self.priority_queue if from_priority else self.queue).appendleft(item)

    async def _run(self: Any) -> None:
        """
        <summary>
        Main output loop. Connects VTube Studio if enabled, then drains the queue,
        blocking normal output while a high-priority audio file is playing.
        </summary>
        """
        if self.vtube_studio_handler and self.app.state.features.vtube_studio:
            self.logger.info("[_run] Connecting to VTube Studio (up to 30s)...")
            try:
                await asyncio.wait_for(
                    self.vtube_studio_handler.ensure_connected(),
                    timeout=30.0,
                )
                await self.vtube_studio_handler.start_idle()
                self.logger.info("[_run] VTube Studio idle animation started.")
            except asyncio.TimeoutError:
                self.logger.warning("[_run] VTube Studio connection timed out after 30s.")
            except Exception as e:
                self.logger.error("[_run] VTube Studio connection failed: %s", e)

        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            while not self.app.state.shutdown.is_set():
                try:
                    item, from_priority = self._pop_next_item()
                    if item is None:
                        await asyncio.sleep(0.05)
                        continue

                    self.logger.info("[_run] Processing item: %s", item)

                    if await self._check_if_timestamp_stale(item):
                        continue

                    if (self.app and self.app.audio_player
                            and self.app.audio_player.is_playing()):
                        await asyncio.sleep(0.2)
                        self._requeue_front(item, from_priority)
                        continue

                    for key in ("prompt", "response"):
                        text = item.get(key)
                        if not text:
                            continue
                        await self._handle_text_output(text)

                except asyncio.CancelledError:
                    self.logger.info("[_run] OutputCoordinator cancelled")
                    break
                except Exception as e:
                    self.logger.exception("[_run] Error: %s", e)
                    await asyncio.sleep(0.1)

    async def _check_if_timestamp_stale(self: Any, item: dict) -> bool:
        """
        <summary>
        Return True if the queued item is older than its allowed age and should be dropped.
        Priority items use priority_max_age; normal items use max_age.
        </summary>
        <param name="item">The queued output item with a 'timestamp' key.</param>
        <returns>True if the item is stale and should be skipped.</returns>
        """
        timestamp = item.get("timestamp")
        if not timestamp:
            self.logger.warning("[_check_if_timestamp_stale] Item missing timestamp, skipping.")
            return True

        max_age = self.priority_max_age if item.get("priority") else self.max_age
        if datetime.now(timezone.utc) - timestamp > max_age:
            self.logger.info("[_check_if_timestamp_stale] Dropping stale output: %s", item)
            return True
        return False

    async def _handle_text_output(self: Any, text: str) -> None:
        """
        <summary>
        Process a single text output: set ai_speaking, run the appropriate visual handler,
        call TTS, then clear ai_speaking and reset the visual handler.
        The only place that drives ai_speaking state.
        </summary>
        <param name="text">The text to speak.</param>
        """
        try:
            if self.app:
                self.app.state.ai_speaking.set()

            if self.enable_subtitles and self.obs_handler:
                await self.obs_handler.update_subtitle_text_and_style(new_text=text)

            await self._get_visual_mode()

            if self.tts_handler:
                self.logger.info("[_handle_text_output] Speaking: %s", text)
                features = self.app.state.features if self.app else None
                vts_active = (
                    features
                    and features.vtube_studio
                    and self.vtube_studio_handler is not None
                )
                on_amplitude = self.vtube_studio_handler.inject_mouth if vts_active else None
                await self.tts_handler.speak(text, on_amplitude=on_amplitude)

        finally:
            if self.app:
                self.app.state.ai_speaking.clear()

            if self.vtube_studio_handler:
                await self.vtube_studio_handler.stop_speaking()

            if self.png_handler:
                await self.png_handler.idle()

    async def _handle_png_output(self: Any) -> None:
        """<summary>Trigger the PNG avatar speaking animation.</summary>"""
        await self.png_handler.speak()

    async def _handle_vtube_studio_output(self: Any) -> None:
        """<summary>Trigger the VTube Studio speaking animation.</summary>"""
        await self.vtube_studio_handler.start_speaking()

    async def _get_visual_mode(self) -> None:
        """
        <summary>
        Activate the appropriate visual output mode (VTube Studio or PNG) based on feature flags.
        Logs when no visual mode is enabled.
        </summary>
        """
        if not self.app or not self.app.state:
            self.logger.info("[_get_visual_mode] No visual output mode enabled.")
            return

        features = self.app.state.features
        vtube_enabled = features.vtube_studio
        png_enabled = features.png_output

        if vtube_enabled and self.vtube_studio_handler:
            await self._handle_vtube_studio_output()
        elif png_enabled and self.png_handler:
            await self._handle_png_output()
        else:
            self.logger.info("[_get_visual_mode] No visual output mode enabled.")