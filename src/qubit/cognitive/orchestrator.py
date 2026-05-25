"""
CognitiveOrchestrator (Service) - the narrow brain of the system.

LAYER: Cognitive / Decision

This is the single place in the entire architecture that is allowed to decide
the bot's next high-level action:

- Should we respond to this chat/STT message?
- Should we emit an autonomous monologue?
- Should we stay silent?

It owns exactly three things:
1. A 5-second decision ticker (_run loop inherited from Service)
2. An ActivityTracker that maintains activity scores and priority queue
3. A DecisionEngine that runs behaviours and picks the winner

All other layers are strictly downstream:
- Generation layer only executes intents it receives via ResponsePromptEvent
- Output layer only speaks what it receives via ResponseGeneratedEvent
- Input Processing only filters and forwards raw events

This component must remain thin. Any decision logic belongs in behaviours.
"""

import asyncio

from src.qubit.core.service import Service
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision_engine import DecisionEngine


class CognitiveOrchestrator(Service):
    """
    Thin Service that orchestrates the cognitive decision loop.

    Responsibilities (strictly limited):
    - Subscribe to processed input events and forward them to ActivityTracker
    - Handle frontend commands and update tracker state
    - Every 5 seconds (in _run), invoke DecisionEngine.run_decision_cycle()
    - The DecisionEngine then selects a behaviour, which may publish a
      ResponsePromptEvent or MonologueEvent

    This class must not contain any "should I respond?" logic itself.
    All intelligence lives in the behaviours and the DecisionEngine.
    """

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_handle_input",
        "stt_processed": "_handle_input",
        "user_event_follow": "_handle_input",
        "user_event_subscription": "_handle_input",
        "user_event_raid": "_handle_input",
        "frontend_command": "_handle_frontend_command",
    }

    def __init__(self):
        super().__init__("CognitiveOrchestrator")
        self.tracker = ActivityTracker()
        self.engine = DecisionEngine(self.tracker, self.event_bus)

    async def start(self, app):
        """
        Starts the orchestrator and ensures the DecisionEngine has the live event_bus.
        The engine is recreated here because at __init__ time the bus may not be ready.
        """
        await super().start(app)
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.tracker.features = self.app.state.features
        self.logger.info("[Cognitive] Orchestrator online (tracker + engine)")

    async def _handle_input(self, event):
        """Forward every processed input event to the ActivityTracker for scoring."""
        await self.tracker.handle_input(event, self.app.state.features)

    async def _handle_frontend_command(self, event):
        """Update the tracker with the latest frontend command (e.g. 'monologue')."""
        command = event.data.get("command")
        self.tracker.set_frontend_command(command)
        self.logger.info(f"[Cognitive] Frontend command received → {command}")

    async def _run(self):
        """
        The 5-second decision loop.

        While the app is running and started, this calls the DecisionEngine
        every 5 seconds. The engine evaluates behaviours and may publish
        high-level intents (response_prompt or monologue_prompt).
        """
        while not self.app.state.shutdown.is_set():
            if self.app.state.start.is_set():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(5)

    def toggle_monologue(self, enabled: bool):
        """Convenience toggle for the monologue feature flag (used by frontend/tests)."""
        self.app.state.features["monologue"] = enabled
        self.logger.info(f"[Cognitive] Monologue feature toggled → {enabled}")
