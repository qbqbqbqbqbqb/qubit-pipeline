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

from config.env_config import settings
from src.qubit.core.service import Service
from src.qubit.cognitive.activity.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision.decision_engine import DecisionEngine


class CognitiveOrchestrator(Service):
    SUBSCRIPTIONS = {
        "twitch_chat_processed": "_handle_input",
        "kick_chat_processed": "_handle_input",
        "stt_processed": "_handle_input",
        # Community events arrive after moderation, using the *_processed
        # naming convention that ModerationProcessor publishes.
        "twitch_raid_processed": "_handle_input",
        "twitch_subscription_processed": "_handle_input",
        "twitch_follow_processed": "_handle_input",
        "kick_raid_processed": "_handle_input",
        "kick_subscription_processed": "_handle_input",
        "kick_follow_processed": "_handle_input",
        "frontend_command": "_handle_frontend_command",
    }

    DECISION_INTERVAL_SECONDS = 5.0

    def __init__(self):
        super().__init__("CognitiveOrchestrator")
        # Tracker is built in start() once settings are available for the whitelist.
        self.tracker: ActivityTracker | None = None
        self.engine: DecisionEngine | None = None

    async def start(self, app) -> None:
        await super().start(app)
        self.tracker = ActivityTracker(mention_whitelist=self._build_mention_whitelist())
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.tracker.features = self.app.state.features
        self.logger.info("[Cognitive] Orchestrator online (tracker + engine)")

    @staticmethod
    def _build_mention_whitelist() -> frozenset[str]:
        """
        Build the set of lowercased names that count as a directed mention.

        Seeded from the four name fields already in settings so users don't
        have to re-enter names they've already configured. Any extras go in
        CHAT_MENTION_WHITELIST as a comma-separated string.
        """
        names: set[str] = set()
        for field in (
            settings.twitch_bot_name,
            settings.twitch_streamer_name,
            settings.kick_bot_name,
            settings.kick_streamer_name,
        ):
            if field:
                names.add(field.lower())
        for extra in (settings.chat_mention_whitelist or "").split(","):
            extra = extra.strip().lower()
            if extra:
                names.add(extra)
        return frozenset(names)

    async def _handle_input(self, event) -> None:
        """Forward every processed input event to the ActivityTracker for scoring."""
        await self.tracker.handle_input(event, self.app.state.features)

    async def _handle_frontend_command(self, event) -> None:
        """Update the tracker with the latest frontend command (e.g. 'monologue')."""
        command = event.data.get("command")
        self.tracker.set_frontend_command(command)
        self.logger.info("[Cognitive] Frontend command received -> %s", command)

    async def _run(self) -> None:
        """The decision loop: every DECISION_INTERVAL_SECONDS, run one decision cycle.

        Time decay is applied unconditionally each tick so the activity score
        relaxes correctly even while output is busy and decision cycles are
        gated. Without this, a chat burst followed by a long TTS response
        would leave the busyness score frozen at its peak for the entire
        duration of the speech.
        """
        while not self.app.state.shutdown.is_set():
            self.tracker.apply_time_decay()
            if self._should_run_cycle():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(self.DECISION_INTERVAL_SECONDS)

    def _should_run_cycle(self) -> bool:
        """Gate on whether the app has started AND output isn't currently speaking."""
        if not self.app.state.start.is_set():
            return False
        return not self._is_output_busy()

    def _is_output_busy(self) -> bool:
        """Return True while OutputCoordinator is actively speaking (TTS running)."""
        return self.app.state.ai_speaking.is_set()

    def toggle_monologue(self, enabled: bool) -> None:
        """Convenience toggle for the monologue feature flag (used by frontend/tests)."""
        self.app.state.features.monologue = enabled
        self.logger.info("[Cognitive] Monologue feature toggled -> %s", enabled)
