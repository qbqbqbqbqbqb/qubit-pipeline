import random
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.base import Behavior
from src.utils.log_utils import get_logger


class IdleMonologueBehavior(Behavior):
    """
    Scored proposal behavior for autonomous / idle speech.

    Goals (2026-05):
    - Fires significantly more at low activity (the "quiet stream" feeling).
    - Still allowed to interject occasionally at medium/high activity so the bot
      never feels like a pure reactive Q&A machine.
    - After answering a user at low activity, it gets a short "follow-up" window
      so the monologue feels like natural conversation instead of abrupt stop/start.
    - Returns scored proposals compatible with the new DecisionEngine proposal model.
    """

    def __init__(self):
        super().__init__("IdleMonologue")
        self.base_cooldown = 28.0
        self.logger = get_logger("IdleMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
        features = context.get("features", {})
        if not features.get("monologue", True):
            return None

        activity = float(context.get("activity_score", 0.0))
        time_since_last = float(context.get("time_since_last_autonomous", 999.0))
        time_since_response = float(context.get("time_since_last_user_response", 999.0))

        # === 1. Dynamic eagerness curve (much higher at low activity) ===
        if activity < 1.5:
            eagerness = 0.88
            effective_cooldown = self.base_cooldown * 0.55   # ~15s
        elif activity < 3.5:
            eagerness = 0.72
            effective_cooldown = self.base_cooldown * 0.75
        elif activity < 7.0:
            eagerness = 0.38
            effective_cooldown = self.base_cooldown
        else:
            eagerness = 0.22
            effective_cooldown = self.base_cooldown * 1.2

        # === 2. Follow-up bonus right after responding (low activity only) ===
        # This is the key anti-"boring" mechanism: after answering a human,
        # the bot can naturally continue with its own thought.
        if activity < 4.5 and time_since_response < 22.0 and time_since_last > 8.0:
            eagerness = min(0.95, eagerness + 0.35)
            effective_cooldown = min(effective_cooldown, 9.0)

        # === 3. Cooldown gate (soft) ===
        if time_since_last < effective_cooldown:
            # Still allow a small random "inspiration" chance even inside cooldown
            if random.random() >= 0.07:
                return None

        # === 4. Random spark at higher activity (keeps personality alive) ===
        if activity >= 4.0:
            if random.random() > 0.17:   # ~83% chance to skip at busy times
                return None

        # === 5. Final score ===
        # Base score from eagerness, with small activity decay so very high activity still prefers strong STT responses
        score = eagerness * (1.0 - min(0.4, activity * 0.03))

        # Extra random jitter for organic feel (never negative)
        score += random.uniform(-0.04, 0.06)
        score = max(0.05, min(1.35, score))

        topic = self._get_topic()
        self.logger.info(f"[IdleMonologue] PROPOSAL | score={score:.3f} | activity={activity:.1f} | topic={topic}")

        return {
            "type": "monologue",
            "score": score,
            "reason": "idle_monologue",
            "topic": topic,
        }

    def _get_topic(self) -> str:
        topics = [
            "a funny story about AI",
            "an interesting Twitch fact",
            "a quirky joke",
            "something weird that happened in the code today",
            "a random observation about streaming",
        ]
        return random.choice(topics)
