import asyncio
from src.qubit.core.service import Service
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision_engine import DecisionEngine

class CognitiveService(Service):

    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_handle_input",
        "stt_processed": "_handle_input",
        "user_event_follow": "_handle_input",
        "user_event_subscription": "_handle_input",
        "user_event_raid": "_handle_input",
        "frontend_command": "_handle_frontend_command",
    }

    def __init__(self, inactivity_timeout=120):
        super().__init__("CognitiveService")
        self.inactivity_timeout = inactivity_timeout

        self.tracker = ActivityTracker()
        self.engine = DecisionEngine(self.tracker, self.event_bus)

    async def start(self, app):
        await super().start(app)
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.logger.info("[Cognitive] Split controller online (tracker + engine)")

    async def _handle_input(self, event):
        await self.tracker.handle_input(event, self.app.state.features)


    async def _run(self):
        while not self.app.state.shutdown.is_set():
            if self.app.state.start.is_set():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(5)


    def toggle_monologue(self, enabled: bool):
        self.app.state.features["monologue"] = enabled
        self.logger.info(f"[Cognitive] Monologue toggled → {enabled}")


    async def _handle_frontend_command(self, event):
        self._current_frontend_command = event.data.get("command")
        self.logger.info(f"[Cognitive] Frontend command received: {self._current_frontend_command}")

    def get_current_frontend_command(self):
        cmd = getattr(self, "_current_frontend_command", None)
        self._current_frontend_command = None
        return cmd