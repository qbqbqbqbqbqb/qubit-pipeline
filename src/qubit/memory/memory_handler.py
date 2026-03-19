"""
Memory event handling utilities.

This module defines the ``MemoryHandler`` which routes processed events
to the memory subsystem. It converts application events into normalized
conversation records and forwards them to ``MemoryService`` for storage.

The handler maps event types to specialized processing methods that
extract relevant fields and attach metadata such as timestamps and
event sources.

Typical event sources include:

- Processed Twitch chat messages
- Viewer interactions (follows, subscriptions)
- Generated AI responses
- Internal monologue prompts
"""
from typing import Any

from src.utils.log_utils import get_logger

class MemoryHandler:
    """
    Route application events to the memory service.

    The handler inspects incoming events, determines whether they should
    be recorded in memory, and normalizes them into conversation entries
    before forwarding them to ``MemoryService``.

    Each supported event type is mapped to a handler method that extracts
    relevant information and attaches metadata describing the event
    source.

    Attributes
    ----------
    logger : logging.Logger
        Logger used for event processing and debugging.
    memory_service : MemoryService
        Service responsible for persisting conversation items.
    routes : dict
        Mapping of event types to handler methods.
    """

    def __init__(self: Any, memory_service: Any): # circular import if i instantiate type,
                                                  #TODO: find out if theres a better way to organise RAG to solve this
        self.logger = get_logger("MemoryHandler")
        self.memory_service = memory_service

        self.routes = {
            "twitch_chat_processed": self.chat_memory,
            "twitch_subscription_processed": self.event_memory,
            "twitch_follow_processed": self.event_memory,
            "monologue_prompt": self.monologue_memory,
            "start_message": self.monologue_memory,
            "response_generated": self.response_memory,
        }

    def handle_event(self, event):
        self.logger.info("[handle_event] Handling memory event %s", event)
        event_type = getattr(event, "type", None)

        handler = self.routes.get(event_type)

        if handler:
            handler(event)
        else:
            self.logger.info("[handle_event] Can't convert %s to memory", event)


    def chat_memory(self, event):
        """Store viewer chat"""
        self.logger.info("[chat_memory] Handling chat memory event")
        self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=event.user,
            metadata={"source": "chat", "timestamp": getattr(event, "timestamp", None)}
        )

    def response_memory(self, event):
        """Store AI responses"""
        self.logger.info("[response_memory] Handling response memory event")
        self.memory_service.add_conversation_item(
            "Qubit",
            event.response,
            metadata={"source": "response", "timestamp": getattr(event, "timestamp", None)}
        )

    def event_memory(self, event):
        """Store notable viewer events"""
        self.logger.info("[event_memory] Handling input event memory event")
        text = f"{event.user} triggered {event.type}"

        self.memory_service.add_conversation_item(
            "User",
            text,
            user_id=event.user,
            metadata={"source": "event", "timestamp": getattr(event, "timestamp", None)}
        )

    def monologue_memory(self, event):
        """AI thoughts"""
        self.logger.info("[monologue_memory] Handling monologue memory event")
        self.memory_service.add_conversation_item(
            "System",
            event.prompt,
            metadata={"source": "monologue", "timestamp": getattr(event, "timestamp", None)}
        )
