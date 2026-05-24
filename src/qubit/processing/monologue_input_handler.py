"""
Monologue input handling service.

This module defines the ``MonologueInputHandler`` service, which processes
incoming ``monologue_prompt`` events and routes them through the system's
prompt and memory pipelines.

Responsibilities
----------------
The handler acts as an intermediary between raw input events and downstream
processing systems. Its core responsibilities include:

- Validating and filtering incoming events (e.g., dropping stale messages).
- Forwarding events to the memory subsystem for persistence or context tracking.
- Converting events into prompt events using registered prompt builders.
- Enqueuing generated prompt events for further processing by the prompt
  dispatcher.

The service integrates with the application's event-driven architecture via
the base ``Service`` class and subscribes to the ``monologue_prompt`` event
type.

Notes
-----
This handler mirrors the behavior of other input handlers (such as chat input
handlers). Some logic may be consolidated into shared base classes in the
future to reduce duplication.
"""

from datetime import datetime, timedelta, timezone
from src.qubit.core.event_processor import EventProcessor
from src.qubit.utils.message_tracker import MessageTracker


class AutonomousInputHandler(EventProcessor):
    """
    Service responsible for handling incoming monologue-style prompt events.

    This service processes events of type ``monologue_prompt`` and performs
    three main actions:

    1. Filters out stale messages based on a configurable age threshold.
    2. Passes events to the memory handler for persistence or contextual tracking.
    3. Converts valid events into prompt events using the prompt handler and
       enqueues them for downstream processing.

    The handler acts as a lightweight bridge between raw input events and the
    prompt generation pipeline.

    Attributes
    ----------
    max_age : timedelta
        Maximum allowed age for incoming events before they are considered stale.
    message_tracker : MessageTracker
        Utility for tracking messages if needed for deduplication or state.
    prompt_handler : Optional[Any]
        Handler responsible for building and dispatching prompt events.
    memory_handler : Optional[Any]
        Handler responsible for storing or processing events for memory systems.
    """

    SUBSCRIPTIONS = {
        "monologue_prompt": "handle_event",
        "start_message": "handle_event",
    }

    def __init__(self, max_age_seconds: int = 30, prompt_handler=None, memory_handler=None):
        """
        Initialize the AutonomousInputHandler service.

        Parameters
        ----------
        max_age_seconds : int, optional
            Maximum allowed age of incoming events in seconds before they are
            discarded as stale.
        prompt_handler : Optional[Any]
            Component responsible for converting events into prompt events and
            enqueueing them for processing.
        memory_handler : Optional[Any]
            Component responsible for handling memory-related updates triggered
            by incoming events.
        """
        super().__init__("monologue handler")
        self.max_age = timedelta(seconds=max_age_seconds)
        self.message_tracker = MessageTracker()
        self.prompt_handler = prompt_handler
        self.memory_handler = memory_handler

    # TODO: consolidate redundant methods btwn input handlers here later
    async def handle_event(self, event) -> None:
        """
        Primary event handler for monologue prompt events.

        The handler performs the following steps:

        1. Normalizes the event text.
        2. Checks whether the message is stale.
        3. Passes the event to the memory handler if configured.
        4. Builds and enqueues a prompt event for downstream processing.

        Parameters
        ----------
        event : Event
            The incoming event containing monologue text and metadata.
        """
        text = event.data.get("text", "").lower().strip()

        if await self._check_stale_message(event, text):
            return

        await self._handle_memory_event(event)
        await self._enqueue_event_prompt(event)

    async def _check_stale_message(self, event, text: str) -> bool:
        """
        Determine whether an incoming event is too old to process.

        The event timestamp is compared against the current time using the
        configured ``max_age`` threshold. Stale events are logged and ignored.

        Parameters
        ----------
        event : Event
            The incoming event containing timestamp metadata.
        text : str
            Normalized text content of the event, used for logging.

        Returns
        -------
        bool
            True if the message is stale and should be dropped, otherwise False.
        """
        ts = getattr(event, "timestamp", datetime.now(timezone.utc))
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        if datetime.now(timezone.utc) - ts > self.max_age:
            self.logger.debug("[_check_stale_message] Dropping stale monologue: %s", text)
            return True
        return False

    async def _enqueue_event_prompt(self, event) -> None:
        """
        Convert event into a prompt and enqueue it for the dispatcher.
        """
        if self.prompt_handler and event.type in self.prompt_handler.builders:
            builder = self.prompt_handler.builders[event.type]
            prompt_event = builder(event)
            await self.prompt_handler.dispatcher.enqueue(prompt_event)
        else:
            self.logger.warning("[MonologueHandler] No prompt builder found for event type: %s", event.type)

    async def _handle_memory_event(self, event) -> None:
        """
        Forward event to memory system if configured.
        """
        if self.memory_handler:
            self.memory_handler.handle_event(event)
