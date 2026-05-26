"""
Conversation input processor (EventProcessor).

LAYER: Input Processing (see ARCHITECTURE.md)

Responsibilities (current transitional state):
- Deduplication of recent chat-style messages (via MessageTracker)
- Staleness filtering (drop events older than max_age)
- Forwarding qualifying events to the memory writer
- (Intentionally does NOT decide whether to respond — that is Cognitive)

Prompt request creation for viewer messages is driven by the
Cognitive layer (DecisionEngine → ResponsePromptEvent → GenerationCoordinator).

This class performs only dedup + staleness + memory forwarding for conversational
input. It has no involvement in prompt building.
"""

from datetime import timedelta

from src.qubit.core.event_processor import EventProcessor
from src.qubit.processing.common import is_stale, forward_to_memory
from src.qubit.utils.message_tracker import MessageTracker


class ConversationProcessor(EventProcessor):
    """
    Pure EventProcessor responsible for conversational input events.

    Responsibilities:
    - Deduplicates recent messages using MessageTracker (prevents repeat spam)
    - Drops stale events older than max_age_seconds
    - Forwards qualifying events to MemoryWriter for long-term storage

    This processor deliberately does **not** decide whether to respond.
    That decision belongs exclusively in the Cognitive layer
    (DecisionEngine + Behaviours).

    After processing, chat events may result in a ResponsePromptEvent
    being published later by the Cognitive layer.
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "twitch_subscription_processed": "handle_event",
        "twitch_raid_processed": "handle_event",
        "twitch_follow_processed": "handle_event",
        "kick_chat_processed": "handle_event",
        "kick_subscription_processed": "handle_event",
        "kick_raid_processed": "handle_event",
        "kick_follow_processed": "handle_event",
        "stt_processed": "handle_event",
    }

    def __init__(self, max_age_seconds=30, memory_writer=None):
        """
        Args:
            max_age_seconds: Events older than this are dropped as stale.
            memory_writer: Optional MemoryWriter to forward events for long-term storage.
        """
        super().__init__("conversation processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.memory_writer = memory_writer

    async def handle_event(self, event) -> None:
        """
        Main entry point for conversational events.

        Applies deduplication, staleness filtering, and memory forwarding.
        Does not publish any ResponsePromptEvent — that is the Cognitive layer's job.
        """
        self.logger.info("[handle_event] Handling event in ConversationProcessor (Cognitive-controlled mode)")

        text = event.data.get("text", "").lower().strip()

        if self._is_repeated(text):
            return

        self._track_message(text)

        if await is_stale(event, self.max_age, self.logger, context="chat"):
            return

        await forward_to_memory(event, self.memory_writer, self.logger)

    def _is_repeated(self, text: str) -> bool:
        """Returns True if this exact text was seen recently (anti-spam)."""
        if self.message_tracker.is_repeated(text):
            self.logger.debug("[_is_repeated] Dropped repeated message: %s", text)
            return True
        return False

    def _track_message(self, text: str) -> None:
        """Records the message text for future deduplication checks."""
        if self.message_tracker:
            self.message_tracker.add_message(text)
