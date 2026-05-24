from datetime import datetime, timezone
from src.qubit.core.event_processor import EventProcessor
from src.qubit.core.events import Event

class FrontendCommandHandler(EventProcessor):
    """
    Thin adapter that normalizes frontend/WebSocket commands 
    into the standard 'frontend_command' event type used by CognitiveService.
    """

    SUBSCRIPTIONS = {
        "bot_started": "handle_event",
    }

    def __init__(self):
        super().__init__("frontend command handler")

    async def handle_event(self, event) -> None:
        """Normalise the frontend commands."""
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
                "raw_event": event.data
            }
        )

        self.logger.info(f"[FrontendCommandHandler] Received frontend command → {command}")
        await self.event_bus.publish(standardised_event)