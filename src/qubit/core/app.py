"""Top-level application container holding services, state, and the event bus."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.qubit.core.event_bus import EventBus
    from src.qubit.core.runtime_state import RuntimeState
    from src.qubit.core.service import Service
    from src.qubit.output.handlers.audio_player import AudioFilePlayer


class App:
    """
    Root application object that owns all services and shared state.

    Constructed in bootstrap.py and passed to every service via attach(app).
    All fields are declared here so readers can see the full contract without
    grepping the codebase.

    Fields set by bootstrap:
        state        RuntimeState — lifecycle events and feature flags
        event_bus    EventBus — the single internal pub/sub bus
        audio_player AudioFilePlayer — exposed for WebSocket and OutputCoordinator
        router       aiohttp.web.Application — set by Kick OAuth during auth only

    Fields managed internally:
        services     ordered list of registered Service instances
    """

    def __init__(self) -> None:
        self.services: list[Service] = []
        self.state: RuntimeState | None = None
        self.event_bus: EventBus | None = None
        self.audio_player: AudioFilePlayer | None = None
        # Set by Kick OAuth auth flow (aiohttp router); None outside that window.
        self.router = None

    def add_service(self, service: Service) -> None:
        """Register a service. Services are started in registration order."""
        self.services.append(service)
