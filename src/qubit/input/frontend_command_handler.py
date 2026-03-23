from src.qubit.core.service import Service
from datetime import datetime, timezone
from src.qubit.core.events import Event

class FrontendCommandHandler(Service):

    def __init__(self):
        super().__init__("FrontendCommandHandler")
    
    SUBSCRIPTIONS = {
        "bot_started": "_handle_raw_command",
    }

    async def start(self, app):
        await super().start(app)
        self.logger.info("[FrontendCommandHandler] Ready — forwarding frontend commands to Cognitive")

    async def _handle_raw_command(self, event):
        """Normalise the startup (and any future) frontend command."""
        raw_command = event.data.get("command", event.type).lower().strip()

        command = "start" if raw_command in ("bot_started", "start") else raw_command

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