"""
<summary>
ConversationProcessor — deduplication and staleness filter for conversational input.
</summary>
<remarks>
LAYER: Input Processing

Responsibilities:
  - Deduplication of recent chat-style messages via MessageTracker.
  - Staleness filtering (drop events older than max_age_seconds).

This processor does not decide whether to respond. That decision belongs
exclusively in the Cognitive layer (DecisionEngine + Behaviours). After
processing, eligible events are available to the Cognitive layer via the
priority queue that ActivityTracker maintains.
</remarks>
"""

from datetime import timedelta

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale
from src.qubit.utils.message_tracker import MessageTracker


class ConversationProcessor(EventProcessor):
    """
    <summary>
    Pure EventProcessor for conversational input events (chat and STT).
    Drops duplicates and stale messages without making any response decisions.
    </summary>
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "kick_chat_processed": "handle_event",
        "stt_processed": "handle_event",
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
        Does not publish any ResponsePromptEvent — that is the Cognitive layer's responsibility.
        </summary>
        <param name="event">The processed conversational event from the bus.</param>
        """
        self.logger.info("[handle_event] Handling event in ConversationProcessor")

        text = event.data.get("text", "").lower().strip()

        if self._is_repeated(text):
            return

        self._track_message(text)

        if await is_stale(event, self.max_age, self.logger, context="chat"):
            return

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
        if self.message_tracker:
            self.message_tracker.add_message(text)
