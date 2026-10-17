"""
<summary>
FrontendCommandProcessor — normalises frontend and lifecycle events into
standard frontend_command events for the Cognitive layer.
</summary>
<remarks>
LAYER: Input Processing

Subscribes to bot_started (internal lifecycle) and frontend_command (WebSocket
commands from the control frontend). Normalises both into a single
frontend_command event type consumed by CognitiveOrchestrator.
</remarks>
"""

from datetime import datetime, timezone

from src.qubit.core.event_processor import EventProcessor
from src.qubit.core.events import Event


class FrontendCommandProcessor(EventProcessor):
    """
    <summary>
    Thin EventProcessor that normalises frontend and lifecycle commands into
    frontend_command events for the Cognitive layer.
    </summary>
    """

    SUBSCRIPTIONS = {
        "bot_started": "handle_event",
        "frontend_command": "handle_event",
    }

    def __init__(self):
        """
        <summary>Initialise the processor and register it with the event bus.</summary>
        """
        super().__init__("frontend command processor")

    async def handle_event(self, event) -> None:
        """
        <summary>
        Normalise a raw frontend or lifecycle event into a standard
        frontend_command event and publish it on the bus.
        </summary>
        <param name="event">The raw event received from the bus.</param>
        """
        raw_command = event.data.get("command", event.type).lower().strip()
        command = "start" if raw_command in ("bot_started", "start", "bot_start") else raw_command

        if not command:
            return

        standardised_event = Event(
            type="frontend_command",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={
                "command": command,
                "source": "frontend",
                "raw_event": event.data,
            },
        )

        self.logger.info("[handle_event] Publishing frontend_command: %s", command)
        await self.event_bus.publish(standardised_event)