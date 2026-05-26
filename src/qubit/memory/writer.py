"""
Memory Writer (pure EventProcessor).

LAYER: Memory (see ARCHITECTURE.md)

This is the dedicated pure reactor responsible for writing events to long-term memory.
It subscribes to processed events that should be persisted and normalizes them
before calling into MemoryService.

Responsibilities (strictly limited to writing):
- Route specific event types to the correct memory storage method
- Normalize chat, responses, viewer events, and monologues into conversation items
- Forward to MemoryService.add_conversation_item

It must remain free of:
- Reading memory for RAG
- Background reflection logic
- Any Service lifecycle (_run loop)

This replaces the old MemoryHandler router as the clean boundary for writes.
"""

from typing import Any

from src.qubit.core.event_processor import EventProcessor
from src.utils.log_utils import get_logger


class MemoryWriter(EventProcessor):
    """
    Pure EventProcessor that writes qualifying events to the memory subsystem.

    It is the single place that decides "this event should become a stored memory item".
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "handle_event",
        "twitch_subscription_processed": "handle_event",
        "twitch_follow_processed": "handle_event",
        "kick_chat_processed": "handle_event",
        "kick_subscription_processed": "handle_event",
        "kick_follow_processed": "handle_event",
        "stt_processed": "handle_event",
        "monologue_prompt": "handle_event",
        "start_message": "handle_event",
        "response_generated": "handle_event",
    }

    def __init__(self, memory_service: Any, stt_speaker_name: str = "Speaker"):
        super().__init__("memory writer")
        self.memory_service = memory_service
        self.stt_speaker_name = stt_speaker_name

        self.routes = {
            "twitch_chat_processed": self._chat_memory,
            "twitch_subscription_processed": self._event_memory,
            "twitch_follow_processed": self._event_memory,
            "kick_chat_processed": self._chat_memory,
            "kick_subscription_processed": self._event_memory,
            "kick_follow_processed": self._event_memory,
            "stt_processed": self._stt_memory,
            "monologue_prompt": self._monologue_memory,
            "start_message": self._monologue_memory,
            "response_generated": self._response_memory,
        }

    async def handle_event(self, event):
        self.logger.info("[handle_event] Handling memory event %s", event)
        event_type = getattr(event, "type", None)

        handler = self.routes.get(event_type)
        if handler:
            handler(event)
        else:
            self.logger.info("[handle_event] Can't convert %s to memory", event)

    def _chat_memory(self, event):
        """Store viewer chat"""
        self.logger.info("[_chat_memory] Handling chat memory event")
        self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=event.user,
            metadata={"source": "chat", "timestamp": getattr(event, "timestamp", None)}
        )

    def _stt_memory(self, event):
        """Store voice input from STT"""
        self.logger.info("[_stt_memory] Handling STT memory event")
        self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=self.stt_speaker_name,
            metadata={"source": "stt", "timestamp": getattr(event, "timestamp", None)}
        )

    def _response_memory(self, event):
        """Store AI responses"""
        self.logger.info("[_response_memory] Handling response memory event")
        self.memory_service.add_conversation_item(
            "Qubit",
            event.response,
            metadata={"source": "response", "timestamp": getattr(event, "timestamp", None)}
        )

    def _event_memory(self, event):
        """Store notable viewer events"""
        self.logger.info("[_event_memory] Handling input event memory event")
        text = f"{event.user} triggered {event.type}"

        self.memory_service.add_conversation_item(
            "User",
            text,
            user_id=event.user,
            metadata={"source": "event", "timestamp": getattr(event, "timestamp", None)}
        )

    def _monologue_memory(self, event):
        """AI thoughts / system monologues"""
        self.logger.info("[_monologue_memory] Handling monologue memory event")
        self.memory_service.add_conversation_item(
            "System",
            event.prompt,
            metadata={"source": "monologue", "timestamp": getattr(event, "timestamp", None)}
        )
