"""Output Coordinator.

LAYER: Output (see ARCHITECTURE.md)

This is the central coordinator for all final output:
- Receives ResponseGeneratedEvent
- Sanitises dialogue (via DialogueSanitiser)
- Owns the output queue + staleness handling
- Coordinates TTS + OBS subtitles + optional VTuber mouth animation
- Owns and drives ai_speaking / ai_thinking state in RuntimeState

It deliberately delegates the actual work to pure leaf handlers:
- TTSHandler
- OBSHandler
- (optional) VTubeStudioHandler
- DialogueSanitiser

This class should only coordinate — it should not contain low-level synthesis,
websocket logic, or sanitiser rules.

--- Priority queue (added) ---
Two deques instead of one: `priority_queue` for community-event reactions
(raids/gifts/follows), `queue` for everything else. The priority queue is
always drained first, and gets a much longer staleness allowance
(PRIORITY_MAX_AGE_SECONDS) — these are rare and shouldn't get silently
dropped just because they waited behind a couple of chat responses.
Detection of "is this a community event" reads event.data["kind"], set by
Cognitive's DecisionExecutor — this only works if Generation forwards
`data` through unchanged when constructing ResponseGeneratedEvent. If it
doesn't, this falls back to normal-priority handling silently; worth
confirming against the actual Generation code.

Both deques are now capped (maxlen). Uncapped, a sustained output stall
(TTS hung, audio_player busy for a long time) lets this grow without bound,
since Cognitive isn't currently throttled by output being busy either (see
CognitiveOrchestrator._is_output_busy(), still a placeholder as of the
cognitive-layer refactor). The maxlen here is a backstop, not a fix for
that — the real fix is wiring that gate so Cognitive stops proposing new
output while a stall is ongoing.
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
    Central coordinator for the entire output pipeline.

    Responsibilities (narrowed per target architecture):
    - Own the response queue and staleness logic
    - Sanitise + forward to memory
    - Drive ai_speaking / ai_thinking state on RuntimeState
    - Coordinate the leaf implementations (TTS, OBS, VTube)

    It must not contain the implementation details of speech synthesis,
    OBS websocket commands, or banned-word lists.
    """

    SUBSCRIPTIONS = {
        "response_generated": "handle_response"
    }

    # Defaults for the split queues — see module docstring for why there
    # are two, and why both are capped.
    DEFAULT_QUEUE_MAXLEN = 40
    DEFAULT_PRIORITY_QUEUE_MAXLEN = 20
    DEFAULT_PRIORITY_MAX_AGE_SECONDS = 120

    def __init__(self: Any,
                 tts_handler: TTSHandler,
                 obs_handler: OBSHandler,
                 vtube_studio_handler=None,
                 max_age_seconds:int=30,
                 priority_max_age_seconds:int=DEFAULT_PRIORITY_MAX_AGE_SECONDS,
                 queue_maxlen:int=DEFAULT_QUEUE_MAXLEN,
                 priority_queue_maxlen:int=DEFAULT_PRIORITY_QUEUE_MAXLEN,
                 enable_subtitles:bool=False,
                 memory_writer=None):
        super().__init__("output_coordinator")
        self.tts_handler = tts_handler
        self.obs_handler = obs_handler
        self.vtube_studio_handler = vtube_studio_handler
        self.png_handler: PNGOutputHandler = None
        self.memory_writer = memory_writer
        self.dialogue_sanitiser = DialogueSanitiser(blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST)

        # Normal-priority items (chat responses, idle monologues, frontend
        # commands). Priority items (raid/gift/follow reactions) go in
        # self.priority_queue instead and are always drained first.
        self.queue = deque(maxlen=queue_maxlen)
        self.priority_queue = deque(maxlen=priority_queue_maxlen)

        self.max_age = timedelta(seconds=max_age_seconds)
        self.priority_max_age = timedelta(seconds=priority_max_age_seconds)
        self.enable_subtitles = enable_subtitles

    async def start(self: Any, app: Any) -> None:
        """Start the output handler service.

        Args:
            app (Any): Reference to the application instance.
        """
        await super().start(app)

        # Block startup until VTube Studio auth succeeds or times out
        if self.vtube_studio_handler and self.app.state.features.get("vtube_studio", True):
            print("[OutputCoordinator] Waiting for VTube Studio connection (up to 30s)...")
            try:
                await asyncio.wait_for(
                    self.vtube_studio_handler.ensure_connected(),
                    timeout=30.0
                )
                # Once connected, start idle animation automatically
                await self.vtube_studio_handler.start_idle()
                print("[OutputCoordinator] VTube Studio idle animation started.")
            except asyncio.TimeoutError:
                print("[OutputCoordinator] VTube Studio connection timed out after 30s. Continuing without it.")
            except Exception as e:
                print(f"[OutputCoordinator] VTube Studio connection failed: {e}")

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

        def _log_mutation(step: str, before: str, after: str):
            if after != before:
                self.logger.info("[handle_response] %s changed text: %r -> %r", step, before, after)

        after_bot = self.dialogue_sanitiser.remove_bot_name(filtered_response)
        _log_mutation("remove_bot_name", filtered_response, after_bot)

        #after_trailing = self.dialogue_sanitiser.remove_trailing_text(after_bot)
        #_log_mutation("remove_trailing_text", after_bot, after_trailing)
        after_trailing = after_bot
        # testing keeping trailing text for now

        response_clean = self.dialogue_sanitiser.strip_leading_punctuation(after_trailing)
        _log_mutation("strip_leading_punctuation", after_trailing, response_clean)

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
        """Forward the event to the memory writer if available.

        Args:
            event (ResponseGeneratedEvent): Event to store in memory.
        """
        if self.memory_writer:
            await self.memory_writer.handle_event(event)

    def _is_priority_event(self: Any, event: ResponseGeneratedEvent) -> bool:
        """
        Best-effort detection of a community-event (raid/gift/follow)
        reaction. Depends on Generation forwarding `data` from the
        originating MonologueEvent through to ResponseGeneratedEvent
        unchanged — if Generation builds `data` fresh instead of passing it
        through, this never triggers and community events silently fall
        back to normal-priority handling. Verify against the actual
        Generation layer.
        """
        data = getattr(event, "data", None) or {}
        return data.get("kind") == "community_event"

    async def _append_to_queue(self: Any, event: ResponseGeneratedEvent) -> None:
        """Append a response event to the appropriate output queue with timestamp.

        Args:
            event (ResponseGeneratedEvent): Event to append.
        """
        is_priority = self._is_priority_event(event)
        target_queue = self.priority_queue if is_priority else self.queue

        if event.source in ("twitch_chat_processed", "kick_chat_processed") and event.prompt:
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

        # deque(maxlen=...) evicts the oldest item automatically once full —
        # no manual bound-checking needed here.
        target_queue.append(item)

    def _pop_next_item(self: Any) -> tuple:
        """Priority queue drains first, whenever it's non-empty."""
        if self.priority_queue:
            return self.priority_queue.popleft(), True
        if self.queue:
            return self.queue.popleft(), False
        return None, False

    def _requeue_front(self: Any, item: dict, from_priority: bool) -> None:
        """Push an item back to the front of whichever queue it came from."""
        (self.priority_queue if from_priority else self.queue).appendleft(item)

    async def _run(self: Any) -> None:
        """Main loop processing the output queues asynchronously."""
        await super()._run()
        while not self.app.state.shutdown.is_set():
            if not self.app.state.start.is_set():
                await asyncio.sleep(1)
                continue

            self.logger.info("[_run] OutputCoordinator started")
            while True:
                try:
                    item, from_priority = self._pop_next_item()
                    if item is None:
                        await asyncio.sleep(0.05)
                        continue

                    self.logger.info("[_run] Processing item: %s", item)

                    if await self._check_if_timestamp_stale(item):
                        continue

                    # Block normal output while high-priority audio file is playing
                    if (self.app and hasattr(self.app, "audio_player")
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
                    self.logger.exception("[_run] Error in OutputCoordinator: %s", e)
                    await asyncio.sleep(0.1)


    async def _check_if_timestamp_stale(self: Any, item: dict) -> bool:
        """Check if the queued item is too old and should be dropped.

        Priority items (community events) get priority_max_age instead of
        the normal max_age — they're rare enough that it's worth tolerating
        a longer wait behind a backlog rather than dropping them.

        Args:
            item (dict): Queued output item with timestamp.

        Returns:
            bool: True if the item is stale and should be ignored.
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
        Process a single text output.

        This is the single place that drives ai_speaking state.
        """
        try:
            if self.app and hasattr(self.app, "state"):
                self.app.state.ai_speaking.set()

            if self.enable_subtitles and self.obs_handler:
                await self.obs_handler.update_subtitle_text_and_style(new_text=text)

            await self._get_visual_mode()

            if self.tts_handler:
                self.logger.info("[_handle_text_output] Speaking: %s", text)
                await self.tts_handler.speak(text)

        finally:
            if self.app and hasattr(self.app, "state"):
                self.app.state.ai_speaking.clear()

            if self.vtube_studio_handler:
                await self.vtube_studio_handler.stop_speaking()

            if self.png_handler:
                await self.png_handler.idle()

    async def _handle_png_output(self: Any) -> None:
            await self.png_handler.speak()

    async def _handle_vtube_studio_output(self:Any) -> None:
            await self.vtube_studio_handler.start_speaking()

    async def _get_visual_mode(self) -> None:
        if not getattr(self.app, "state", None):
            self.logger.info("[_get_visual_mode] No visual output mode enabled.")
            return

        features = self.app.state.features
        vtube_enabled = features.get("vtube_studio", False)
        png_enabled = features.get("png_output", False)

        if vtube_enabled and self.vtube_studio_handler:
            await self._handle_vtube_studio_output()
        elif png_enabled and self.png_handler:
            await self._handle_png_output()
        else:
             self.logger.info("[_get_visual_mode] No visual output mode enabled.")