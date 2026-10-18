"""
<summary>
MemoryWriter — pure EventProcessor responsible for writing qualifying events to long-term memory.
</summary>
<remarks>
LAYER: Memory

Single place that decides "this event should become a stored memory item."
Routes specific event types to the correct MemoryService storage method.

Must remain free of:
  - Reading memory for RAG (that is MemoryService's responsibility)
  - Background reflection logic
  - Any Service lifecycle (_run loop)
</remarks>
"""

from typing import Any

from src.qubit.core.event_processor import EventProcessor
from src.qubit.utils.log_utils import get_logger


class MemoryWriter(EventProcessor):
    """
    <summary>
    Pure EventProcessor that normalises and writes qualifying events into MemoryService.
    </summary>
    """

    SUBSCRIPTIONS = {
        # Chat and STT: subscribe to filtered variants so only deduplicated,
        # non-stale messages are written to memory.
        "twitch_chat_filtered": "handle_event",
        "kick_chat_filtered": "handle_event",
        "stt_filtered": "handle_event",
        # Community events skip ConversationProcessor and stay on *_processed.
        "twitch_subscription_processed": "handle_event",
        "twitch_follow_processed": "handle_event",
        "kick_subscription_processed": "handle_event",
        "kick_follow_processed": "handle_event",
        "monologue_prompt": "handle_event",
        "response_generated": "handle_event",
    }

    def __init__(self, memory_service: Any, stt_speaker_name: str = "Speaker", runtime_state=None):
        """
        <summary>Initialise the writer with its target memory service and STT speaker name.</summary>
        <param name="memory_service">The MemoryService instance to write to.</param>
        <param name="stt_speaker_name">Display name used as user_id for STT items.</param>
        """
        super().__init__("memory writer")
        self.memory_service = memory_service
        self.stt_speaker_name = stt_speaker_name
        self.runtime_state = runtime_state

        self.routes = {
            "twitch_chat_filtered": self._chat_memory,
            "kick_chat_filtered": self._chat_memory,
            "stt_filtered": self._stt_memory,
            "twitch_subscription_processed": self._event_memory,
            "twitch_follow_processed": self._event_memory,
            "kick_subscription_processed": self._event_memory,
            "kick_follow_processed": self._event_memory,
            "monologue_prompt": self._monologue_memory,
            "response_generated": self._response_memory,
        }

    async def handle_event(self, event) -> None:
        """
        <summary>
        Route an incoming event to the appropriate memory storage method.
        When the memory_write feature flag is disabled, the event is acknowledged
        but not persisted — the LLM still responds, but nothing is stored.
        </summary>
        <param name="event">The event to store.</param>
        """
        self.logger.info("[handle_event] Handling memory event %s", event)

        if self.runtime_state and not self.runtime_state.features.memory_write:
            self.logger.debug("[handle_event] memory_write disabled — skipping write for %s", getattr(event, "type", None))
            return

        event_type = getattr(event, "type", None)

        handler = self.routes.get(event_type)
        if handler:
            await handler(event)
        else:
            self.logger.info("[handle_event] No memory route for %s", event_type)

    async def _chat_memory(self, event) -> None:
        """
        <summary>Store a viewer chat message as a User conversation item.</summary>
        <param name="event">The processed chat event (TwitchChatEvent or KickChatEvent).</param>
        """
        self.logger.info("[_chat_memory] Storing chat from %s", event.user)
        await self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=event.user,
            metadata={"source": "chat", "timestamp": getattr(event, "timestamp", None)},
        )

    async def _stt_memory(self, event) -> None:
        """
        <summary>Store voice input from the streamer as a User conversation item.</summary>
        <param name="event">The stt_processed event containing the transcribed text.</param>
        """
        self.logger.info("[_stt_memory] Storing STT input")
        await self.memory_service.add_conversation_item(
            "User",
            event.text,
            user_id=self.stt_speaker_name,
            metadata={"source": "stt", "timestamp": getattr(event, "timestamp", None)},
        )

    async def _response_memory(self, event) -> None:
        """
        <summary>Store Qubit's generated response as a Qubit conversation item.</summary>
        <param name="event">The response_generated event containing the response text.</param>
        """
        self.logger.info("[_response_memory] Storing generated response")
        await self.memory_service.add_conversation_item(
            "Qubit",
            event.response,
            metadata={"source": "response", "timestamp": getattr(event, "timestamp", None)},
        )

    async def _event_memory(self, event) -> None:
        """
        <summary>Store a notable viewer event (subscription, follow) as a User conversation item.</summary>
        <param name="event">The processed platform event.</param>
        """
        self.logger.info("[_event_memory] Storing viewer event %s", event.type)
        text = f"{event.user} triggered {event.type}"
        await self.memory_service.add_conversation_item(
            "User",
            text,
            user_id=event.user,
            metadata={"source": "event", "timestamp": getattr(event, "timestamp", None)},
        )

    async def _monologue_memory(self, event) -> None:
        """
        <summary>Store an autonomous monologue prompt as a System conversation item.</summary>
        <param name="event">The monologue_prompt event containing the prompt text.</param>
        """
        self.logger.info("[_monologue_memory] Storing monologue prompt")
        await self.memory_service.add_conversation_item(
            "System",
            event.prompt,
            metadata={"source": "monologue", "timestamp": getattr(event, "timestamp", None)},
        )
