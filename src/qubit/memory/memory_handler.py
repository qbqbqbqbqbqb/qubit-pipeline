from typing import Any, Optional

from src.utils.log_utils import get_logger

class MemoryHandler:
    """
    Handle incoming events and normalize the role before forwarding
    to the memory service.

    Usage:
        handler = MemoryHandler(memory_service)
        handler.handle_event(event)
    """

    def __init__(self, memory_service: Any):
        self.logger = get_logger("MemoryHandler")
        self.memory_service = memory_service

        self.routes = {
            "twitch_chat_processed": self.chat_memory,
            "twitch_subscription_processed": self.event_memory,
            "twitch_follow_processed": self.event_memory,
            "monologue_prompt": self.monologue_memory,
            "response_generated": self.response_memory,
        }

    def handle_event(self, event):
        self.logger.info(f"Handling memory event {event}")
        event_type = getattr(event, "type", None)

        handler = self.routes.get(event_type)

        if handler:
            handler(event)
        else:
            self.logger.info(f"Can't convert {event} to memory")


    def chat_memory(self, event):
        """Store viewer chat"""
        self.logger.info("Handling chat memory event")
        self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=event.user,
            metadata={"source": "chat", "timestamp": getattr(event, "timestamp", None)}
        )

    def response_memory(self, event):
        """Store AI responses"""
        self.logger.info("Handling response memory event")        
        self.memory_service.add_conversation_item(
            "Qubit",
            event.response,
            metadata={"source": "response", "timestamp": getattr(event, "timestamp", None)}
        )

    def event_memory(self, event):
        """Store notable viewer events"""
        self.logger.info("Handling input event memory event")
        text = f"{event.user} triggered {event.type}"

        self.memory_service.add_conversation_item(
            "User",
            text,
            user_id=event.user,
            metadata={"source": "event", "timestamp": getattr(event, "timestamp", None)}
        )

    def monologue_memory(self, event):
        """AI thoughts"""
        self.logger.info("Handling monologue memory event")
        self.memory_service.add_conversation_item(
            "Qubit",
            event.prompt,
            metadata={"source": "monologue", "timestamp": getattr(event, "timestamp", None)}
        )
