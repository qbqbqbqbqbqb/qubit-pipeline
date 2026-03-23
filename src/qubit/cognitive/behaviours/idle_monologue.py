import random
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.base import Behavior, BehaviorContext
from src.qubit.core.events import MonologueEvent
from src.utils.log_utils import get_logger

class IdleMonologueBehavior(Behavior):
    def __init__(self):
        super().__init__("IdleMonologue")
        self.cooldown_seconds = 30  # lowered for testing
        self.logger = get_logger("IdleMonologueBehavior")

    async def tick(self, context: dict) -> dict | None:
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
        prompt = f"Talk about {topic}."

        self.logger.info(f"[IdleMonologue] TRIGGERED ({reason}) → {topic}")

        return MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=now.isoformat(),
            data={
                "user": "system",
                "topic": topic,
                "reason": reason,
                "prompt": prompt,
            },
            prompt=prompt,
        )

    def _get_topic(self) -> str:
        topics = [
            "a funny story about AI",
            "an interesting Twitch fact",
            "a quirky joke",
        ]
        return random.choice(topics)