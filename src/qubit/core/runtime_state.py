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
    """
    Single source of truth for all cross-cutting runtime state.

    This object is intentionally mutable and shared. It holds:
    - Lifecycle events (start, shutdown)
    - Feature toggles (can be changed live from the frontend)
    - AI activity signals (ai_speaking, ai_thinking) — these are set/cleared
      exclusively by the Output layer when speech is actually happening.

    No other component should duplicate these flags. All layers read from
    or react to this state (or the events it drives).
    """

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
