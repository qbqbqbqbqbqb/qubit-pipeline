"""
<summary>
CognitiveOrchestrator — the single authority on Qubit's next high-level action.
</summary>
<remarks>
LAYER: Cognitive / Decision

The only component in the architecture permitted to decide what the bot does next:
respond to chat or STT input, emit an autonomous monologue, or stay silent.

Owns exactly three things:
  1. A decision ticker (_run loop inherited from Service)
  2. An ActivityTracker that maintains activity scores and the priority queue
  3. A DecisionEngine that runs behaviours and selects a winner

All other layers are strictly downstream:
  - Generation layer executes intents received via ResponsePromptEvent
  - Output layer speaks what it receives via ResponseGeneratedEvent
  - Input Processing only filters and forwards raw events

This component must remain thin. Any decision logic belongs in behaviours.
</remarks>
"""

import asyncio

from config.env_config import settings
from src.qubit.core.service import Service
from src.qubit.cognitive.activity.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision.decision_engine import DecisionEngine


class CognitiveOrchestrator(Service):
    """
    <summary>
    Service that runs the cognitive decision loop and coordinates ActivityTracker
    and DecisionEngine.
    </summary>
    """

    SUBSCRIPTIONS = {
        # Chat and STT arrive after ConversationProcessor dedup/staleness filter.
        "twitch_chat_filtered": "_handle_input",
        "kick_chat_filtered": "_handle_input",
        "stt_filtered": "_handle_input",
        # Community events are not conversational and skip ConversationProcessor.
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
        self.tracker: ActivityTracker | None = None
        self.engine: DecisionEngine | None = None

    def attach(self, app) -> None:
        """
        <summary>
        Bind to the app, then construct ActivityTracker and DecisionEngine
        with the configured mention whitelist.
        </summary>
        <param name="app">The root App instance.</param>
        """
        super().attach(app)
        self.tracker = ActivityTracker(mention_whitelist=self._build_mention_whitelist())
        self.engine = DecisionEngine(self.tracker, self.event_bus)
        self.tracker.features = self.app.state.features
        self.logger.info("[Cognitive] Orchestrator online (tracker + engine)")

    @staticmethod
    def _build_mention_whitelist() -> frozenset[str]:
        """
        <summary>
        Build the set of lowercased names that count as a directed mention.
        Seeded from the four name fields in settings plus any extras in
        CHAT_MENTION_WHITELIST (comma-separated).
        </summary>
        <returns>A frozenset of lowercased name strings.</returns>
        """
        names: set[str] = set()
        for name_field in (
            settings.twitch_bot_name,
            settings.twitch_streamer_name,
            settings.kick_bot_name,
            settings.kick_streamer_name,
        ):
            if name_field:
                names.add(name_field.lower())
        for extra in (settings.chat_mention_whitelist or "").split(","):
            extra = extra.strip().lower()
            if extra:
                names.add(extra)
        return frozenset(names)

    async def _handle_input(self, event) -> None:
        """
        <summary>Forward every processed input event to the ActivityTracker for scoring.</summary>
        <param name="event">The processed input event from the bus.</param>
        """
        await self.tracker.handle_input(event, self.app.state.features)

    async def _handle_frontend_command(self, event) -> None:
        """
        <summary>Update the tracker with the latest frontend command (e.g. 'monologue').</summary>
        <param name="event">The frontend_command event from the bus.</param>
        """
        command = event.data.get("command")
        self.tracker.set_frontend_command(command)
        self.logger.info("[Cognitive] Frontend command received -> %s", command)

    async def _run(self) -> None:
        """
        <summary>
        Decision loop: every DECISION_INTERVAL_SECONDS, apply time decay and
        optionally run one decision cycle. Time decay runs unconditionally each
        tick so the activity score relaxes correctly even while output is busy.
        </summary>
        """
        while not self.app.state.shutdown.is_set():
            self.tracker.apply_time_decay()
            if self._should_run_cycle():
                await self.engine.run_decision_cycle()
            await asyncio.sleep(self.DECISION_INTERVAL_SECONDS)

    def _should_run_cycle(self) -> bool:
        return self.app.state.start.is_set()