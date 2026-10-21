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
        "bot_end_stream": "handle_event",
        "frontend_command": "handle_event",
    }

    # Commands that toggle a RuntimeState feature flag directly, without being
    # forwarded to the Cognitive layer as frontend_command events.
    _MEMORY_COMMANDS = {
        "toggle_memory_read",
        "toggle_memory_write",
    }

    def __init__(self, runtime_state=None):
        """
        <summary>Initialise the processor and register it with the event bus.</summary>
        <param name="runtime_state">The shared RuntimeState whose feature flags are toggled
        by memory control commands. None disables memory toggle handling.</param>
        """
        super().__init__("frontend command processor")
        self.runtime_state = runtime_state

    async def handle_event(self, event) -> None:
        """
        <summary>
        Normalise a raw frontend or lifecycle event into a standard
        frontend_command event and publish it on the bus.
        </summary>
        <param name="event">The raw event received from the bus.</param>
        """
        raw_command = event.data.get("command", event.type).lower().strip()
        if raw_command in ("bot_started", "start", "bot_start"):
            command = "start"
        elif raw_command in ("bot_end_stream", "end_stream"):
            command = "end_stream"
        else:
            command = raw_command

        if not command:
            return

        if command in self._MEMORY_COMMANDS:
            await self._handle_memory_toggle(command)
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
    async def _handle_memory_toggle(self, command: str) -> None:
        """
        <summary>
        Toggle memory_read or memory_write on RuntimeState.features without
        publishing a frontend_command event — these are internal flag flips
        that do not need the Cognitive layer involved.
        </summary>
        <param name="command">One of 'toggle_memory_read' or 'toggle_memory_write'.</param>
        """
        if not self.runtime_state:
            self.logger.warning("[_handle_memory_toggle] No runtime_state — cannot toggle memory flags")
            return

        if command == "toggle_memory_read":
            self.runtime_state.features.memory_read = not self.runtime_state.features.memory_read
            self.logger.info(
                "[_handle_memory_toggle] memory_read -> %s",
                self.runtime_state.features.memory_read,
            )
        elif command == "toggle_memory_write":
            self.runtime_state.features.memory_write = not self.runtime_state.features.memory_write
            self.logger.info(
                "[_handle_memory_toggle] memory_write -> %s",
                self.runtime_state.features.memory_write,
            )