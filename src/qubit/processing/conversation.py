"""
<summary>
ConversationProcessor — deduplication and staleness filter for conversational input.
</summary>
<remarks>
LAYER: Input Processing

Responsibilities:
  - Deduplication of recent chat-style messages via MessageTracker.
  - Staleness filtering (drop events older than max_age_seconds).
  - Publishing filtered events downstream so the dedup is real.

Input events:
  twitch_chat_processed, kick_chat_processed, stt_processed

Output events (published after passing both filters):
  twitch_chat_filtered, kick_chat_filtered, stt_filtered

Downstream subscribers (CognitiveOrchestrator, EventAdapter, MemoryWriter)
listen to the *_filtered variants so only deduplicated, fresh messages
reach the cognitive layer and memory.

This processor does not decide whether to respond. That decision belongs
exclusively in the Cognitive layer (DecisionEngine + Behaviours).
</remarks>
"""

import dataclasses
from datetime import timedelta

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale
from src.qubit.utils.message_tracker import MessageTracker

# Maps each input event type to the filtered output type it becomes.
_FILTERED_TYPE = {
    "twitch_chat_processed": "twitch_chat_filtered",
    "kick_chat_processed":   "kick_chat_filtered",
    "stt_processed":         "stt_filtered",
}


class ConversationProcessor(EventProcessor):
    """
    <summary>
    EventProcessor for conversational input events (chat and STT).
    Drops duplicates and stale messages, then re-publishes survivors
    as *_filtered events for downstream consumers.
    </summary>
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "kick_chat_processed":   "handle_event",
        "stt_processed":         "handle_event",
    }

    def __init__(self, max_age_seconds=30):
        """
        <summary>Initialise the processor with a staleness window.</summary>
        <param name="max_age_seconds">Events older than this are dropped as stale.</param>
        """
        super().__init__("conversation processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()

    async def handle_event(self, event) -> None:
        """
        <summary>
        Apply deduplication and staleness filtering to a conversational event.
        Passing events are re-published with a *_filtered type so the dedup
        actually gates what the Cognitive layer and MemoryWriter receive.
        </summary>
        <param name="event">The processed conversational event from the bus.</param>
        """
        self.logger.info("[handle_event] Received %s", event.type)

        text = event.data.get("text", "").lower().strip()

        if self._is_repeated(text):
            return

        self._track_message(text)

        if await is_stale(event, self.max_age, self.logger, context="chat"):
            return

        await self._publish_filtered(event)

    async def _publish_filtered(self, event) -> None:
        """
        <summary>
        Re-publish the event with its type changed to the *_filtered variant.
        Uses dataclasses.replace so all other fields are preserved exactly.
        </summary>
        <param name="event">The event that passed all filters.</param>
        """
        filtered_type = _FILTERED_TYPE.get(event.type)
        if filtered_type is None:
            self.logger.warning("[_publish_filtered] No filtered type mapping for %s", event.type)
            return

        filtered_event = dataclasses.replace(event, type=filtered_type)
        self.logger.info("[_publish_filtered] Publishing %s", filtered_type)
        await self.event_bus.publish(filtered_event)

    def _is_repeated(self, text: str) -> bool:
        """
        <summary>Return True if this exact text was seen recently (anti-spam check).</summary>
        <param name="text">Lowercased, stripped message text.</param>
        <returns>True if the message is a recent duplicate.</returns>
        """
        if self.message_tracker.is_repeated(text):
            self.logger.debug("[_is_repeated] Dropped repeated message: %s", text)
            return True
        return False

    def _track_message(self, text: str) -> None:
        """
        <summary>Record the message text for future deduplication checks.</summary>
        <param name="text">Lowercased, stripped message text to record.</param>
        """
        self.message_tracker.add_message(text)
