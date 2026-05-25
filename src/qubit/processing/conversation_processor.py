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
from src.qubit.processing._input_common import is_stale, forward_to_memory
from src.qubit.utils.message_tracker import MessageTracker


class ConversationProcessor(EventProcessor):
    """
    Pure EventProcessor for normal viewer input (chat, subs, raids, follows).

    It performs only the mechanical filtering + memory forwarding steps.
    All decision logic lives in the Cognitive layer.
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "twitch_subscription_processed": "handle_event",
        "twitch_raid_processed": "handle_event",
        "twitch_follow_processed": "handle_event",
    }

    def __init__(self, max_age_seconds=30, memory_writer=None):
        super().__init__("conversation processor")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.memory_writer = memory_writer

    async def handle_event(self, event) -> None:
        self.logger.info("[handle_event] Handling event in ConversationProcessor (Cognitive-controlled mode)")

        text = event.data.get("text", "").lower().strip()

        if self._is_repeated(text):
            return

        self._track_message(text)

        if await is_stale(event, self.max_age, self.logger, context="chat"):
            return

        await forward_to_memory(event, self.memory_writer, self.logger)

    def _is_repeated(self, text: str) -> bool:
        if self.message_tracker.is_repeated(text):
            self.logger.debug("[_is_repeated] Dropped repeated message: %s", text)
            return True
        return False

    def _track_message(self, text: str) -> None:
        if self.message_tracker:
            self.message_tracker.add_message(text)
