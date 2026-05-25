"""
Shared runtime state.

This is the SINGLE source of truth for cross-cutting flags and events that
multiple layers need to observe or control:

- Feature toggles (twitch, monologue, stt, etc.)
- Lifecycle signals (start / shutdown)
- AI activity state (ai_speaking, ai_thinking) — driven by the Output layer

Do not scatter equivalent flags in CognitiveOrchestrator, OutputCoordinator, etc.
All layers should read/write through this object (or events published from it).

See ARCHITECTURE.md — "State" section.
"""

import asyncio


class RuntimeState:
    """Central holder for application-wide runtime flags and events."""

    def __init__(self):
        # Lifecycle
        self.shutdown = asyncio.Event()
        self.start = asyncio.Event()

        # Feature flags (can be toggled live from the WebSocket frontend)
        self.features = {
            "twitch": True,
            "kick": True,
            "youtube": True,
            "stt": True,
            "chat": True,
            "raid": True,
            "follow": True,
            "subs": True,
            "monologue": True
        }

        # Cross-layer activity signals (primarily driven by Output layer)
        self.ai_speaking = asyncio.Event()
        self.ai_thinking = asyncio.Event()
