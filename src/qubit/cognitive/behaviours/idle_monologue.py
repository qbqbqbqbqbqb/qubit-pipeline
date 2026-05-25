import random
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.base import Behavior
from src.qubit.core.events import MonologueEvent
from src.utils.log_utils import get_logger


class IdleMonologueBehavior(Behavior):
    """
    Behavior responsible for emitting low-activity or random idle monologues.

    Part of the cognitive layer's pluggable decision strategies (see DecisionEngine + priority queue).
    Activates primarily in low activity_score (< 3.0) after cooldown, with a small random chance
    even during higher activity.

    Role in 2026 SoC refactor:
    - Isolates monologue trigger rules (activity thresholds, cooldowns, topic selection) from
      the orchestrator and DecisionEngine.
    - Implements the Behavior ABC so behaviours can be composed without changing core decision loop.
    - Complements ChatResponseBehavior (medium activity) and FrontendTriggeredMonologueBehavior.

    Contract:
    - Receives full context dict from DecisionEngine._build_context().
    - Returns {"type": "monologue", "topic": str} or None.
    - Stateless; all timers and features come from context.
    """

    def __init__(self):
        super().__init__("IdleMonologue")
        self.cooldown_seconds = 30  # lowered for testing
        self.logger = get_logger("IdleMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate activity score, timers and random chance to decide on an idle monologue.

        Args:
            context: Snapshot containing activity_score, last_autonomous_speech_time,
                     features dict (with "monologue" flag), etc.

        Returns:
            dict | None: Monologue decision or None.
        """
        now = datetime.now(timezone.utc)
        time_since_last = (now - context["last_autonomous_speech_time"]).total_seconds()

        self.logger.info(f"[IdleMonologue] Check | score={context['activity_score']:.2f} | "
                        f"time_since_last={time_since_last:.0f}s | random={random.random():.3f}")

        if not context["features"].get("monologue", True):
            return None

        # LOW ACTIVITY (your main rule)
        if context["activity_score"] < 3.0 and time_since_last > self.cooldown_seconds:
            topic = self._get_topic()
            return self._build_event(topic, "low_activity", now)

        # RANDOM CHANCE (even when busy)
        if random.random() < 0.18:   # 18% per cycle for testing
            topic = self._get_topic()
            return self._build_event(topic, "low_activity", now)

        return None

    def _build_event(self, topic: str, reason: str, now: datetime):
        """Build the monologue decision dict and log the trigger."""
        prompt = f"Talk about {topic}."

        self.logger.info(f"[IdleMonologue] TRIGGERED ({reason}) → {topic}")

        return {
            "type": "monologue",
            "topic": topic,
        }

    def _get_topic(self) -> str:
        """Return a random topic from the curated idle monologue pool."""
        topics = [
            "a funny story about AI",
            "an interesting Twitch fact",
            "a quirky joke",
        ]
        return random.choice(topics)
