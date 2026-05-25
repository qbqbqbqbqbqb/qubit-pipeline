"""
Cognitive / Decision Layer orchestrator (Service).

LAYER: Cognitive / Decision (see ARCHITECTURE.md)

This is the ONLY component allowed to decide what the bot should do next:
- Respond to a viewer?
- Emit an autonomous monologue?
- Stay silent?

It owns:
- The 5-second decision ticker (_run)
- Wiring of ActivityTracker + DecisionEngine
- Subscription to the raw events that feed decision context

It deliberately does **not** own prompt construction, LLM calls, or output.
Those are delegated to the Generation and Output layers.
"""

import asyncio

from src.qubit.core.service import Service
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision_engine import DecisionEngine


class CognitiveOrchestrator(Service):
    """
    The narrow orchestrator for the cognitive layer.

    Its only jobs are:
    1. Feed every relevant input event into the ActivityTracker
    2. Feed frontend commands into the tracker (as decision context)
    3. Every 5 seconds, ask the DecisionEngine to run one decision cycle

    Nothing else.
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
        await super().start(app)
        # Re-create the engine now that we have the real event_bus
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.logger.info("[Cognitive] Orchestrator online (tracker + engine)")

    async def _handle_input(self, event):
        await self.tracker.handle_input(event, self.app.state.features)

    async def _handle_frontend_command(self, event):
        command = event.data.get("command")
        self.tracker.set_frontend_command(command)
        self.logger.info(f"[Cognitive] Frontend command received → {command}")

    async def _run(self):
        while not self.app.state.shutdown.is_set():
            if self.app.state.start.is_set():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(5)

    # Convenience for external toggles (frontend, tests, etc.)
    def toggle_monologue(self, enabled: bool):
        self.app.state.features["monologue"] = enabled
        self.logger.info(f"[Cognitive] Monologue feature toggled → {enabled}")
