"""
CognitiveOrchestrator (Service) - the narrow brain of the system.

LAYER: Cognitive / Decision

The single place in the entire architecture that is allowed to decide the
bot's next high-level action: respond to chat/STT, emit an autonomous
monologue, or stay silent.

It owns exactly three things:
1. A decision ticker (_run loop inherited from Service)
2. An ActivityTracker that maintains activity scores and priority queue
3. A DecisionEngine that runs behaviours and picks the winner

All other layers are strictly downstream:
- Generation layer only executes intents received via ResponsePromptEvent
- Output layer only speaks what it receives via ResponseGeneratedEvent
- Input Processing only filters and forwards raw events

This component must remain thin. Any decision logic belongs in behaviours.
"""

import asyncio

from src.qubit.core.service import Service
from src.qubit.cognitive.activity.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision.decision_engine import DecisionEngine


class CognitiveOrchestrator(Service):
    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_handle_input",
        "kick_chat_processed": "_handle_input",
        "stt_processed": "_handle_input",
        "user_event_follow": "_handle_input",
        "user_event_subscription": "_handle_input",
        "user_event_raid": "_handle_input",
        "frontend_command": "_handle_frontend_command",
    }

    DECISION_INTERVAL_SECONDS = 5.0

    def __init__(self):
        super().__init__("CognitiveOrchestrator")
        self.tracker = ActivityTracker()
        # Real DecisionEngine is built in start(), once event_bus is live.
        self.engine: DecisionEngine | None = None

    async def start(self, app) -> None:
        await super().start(app)
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.tracker.features = self.app.state.features
        self.logger.info("[Cognitive] Orchestrator online (tracker + engine)")

    async def _handle_input(self, event) -> None:
        """Forward every processed input event to the ActivityTracker for scoring."""
        await self.tracker.handle_input(event, self.app.state.features)

    async def _handle_frontend_command(self, event) -> None:
        """Update the tracker with the latest frontend command (e.g. 'monologue')."""
        command = event.data.get("command")
        self.tracker.set_frontend_command(command)
        self.logger.info("[Cognitive] Frontend command received -> %s", command)

    async def _run(self) -> None:
        """The decision loop: every DECISION_INTERVAL_SECONDS, run one decision cycle."""
        while not self.app.state.shutdown.is_set():
            if self._should_run_cycle():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(self.DECISION_INTERVAL_SECONDS)

    def _should_run_cycle(self) -> bool:
        """
        Gate on whether the app has started AND output isn't currently busy
        speaking.

        NOTE: the speaking check is best-effort. If RuntimeState doesn't
        expose the attribute this looks for, it falls back to "not busy" so
        it never blocks the loop outright — which means the gate is
        currently a no-op until wired to the real flag. Confirm the actual
        attribute path for "currently speaking" on RuntimeState /
        OutputCoordinator and update _is_output_busy() accordingly; this was
        written without visibility into those files.
        """
        if not self.app.state.start.is_set():
            return False
        return not self._is_output_busy()

    def _is_output_busy(self) -> bool:
        runtime = getattr(self.app.state, "runtime", None)
        return bool(getattr(runtime, "ai_speaking", False))

    def toggle_monologue(self, enabled: bool) -> None:
        """Convenience toggle for the monologue feature flag (used by frontend/tests)."""
        self.app.state.features["monologue"] = enabled
        self.logger.info("[Cognitive] Monologue feature toggled -> %s", enabled)