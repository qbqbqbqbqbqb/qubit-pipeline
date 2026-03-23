import random
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.base import Behavior, BehaviorContext
from src.qubit.core.events import MonologueEvent

class IdleMonologueBehavior(Behavior):
    def __init__(self):
        super().__init__("IdleMonologue")
        self.cooldown_seconds = 10

    async def tick(self, context: BehaviorContext) -> dict | None:
        if not await self._should_trigger_monologue(context):
            return None

        topic = await self._get_topic_for_autonomous_speech()
        return self._create_monologue_event(topic)
        # TODO: map out event system to ensure monologues responses  arent dropped when chosen this way

    async def _should_trigger_monologue(self, context: BehaviorContext) -> bool:
        if not context.features.get("monologue", True):
            return False

        return await self._decide_to_trigger_monologue(context)

    async def _create_monologue_event(self, topic):
        prompt = f"Monologue about {topic}, in character as Qubit."
        return MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"user": "system", "topic": topic, "prompt": prompt},
            prompt=prompt,
        )
        
    async def _decide_to_trigger_monologue(self, context: BehaviorContext) -> bool:
        now = datetime.now(timezone.utc)
        time_since_last = (now - context.last_autonomous_speech_time).total_seconds()

        if context.activity_score < 3.0 and time_since_last > self.cooldown_seconds:
            return True
        
        if random.random() < 0.12 and time_since_last > self.cooldown_seconds:
            return True
        
        return False
    
    async def _get_topic_for_autonomous_speech(self):
        topics = [
                            "a funny story about AI",
                            "an interesting Twitch fact",
                            "a quirky joke",
                            "motivational advice",
                            "a short adventure tale"
                        ]
        return random.choice(topics)
    