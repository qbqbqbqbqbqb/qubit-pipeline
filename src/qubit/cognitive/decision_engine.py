import random
from datetime import datetime, timezone

from src.qubit.core.events import MonologueEvent, ResponsePromptEvent
from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.activity_tracker import ActivityTracker


class DecisionEngine:
    """
    Pure decision maker + behavior runner.

    This is the "brain" of the Cognitive layer.
    It receives a pre-built context from the ActivityTracker and runs
    all behaviors in priority order. Only one decision is executed per cycle
    to prevent conflicting actions (monologue + response at the same time).
    """

    def __init__(self, tracker: ActivityTracker, event_bus):
        """
        Initialize the decision engine.

        Args:
            tracker: ActivityTracker instance that holds score + priority queue
            event_bus: The central event bus used to publish final decisions
        """
        self.tracker = tracker
        self.event_bus = event_bus

        # Behaviors are ordered by priority (monologue first, then responses)
        self.behaviors = [IdleMonologueBehavior(), ChatResponseBehavior()]

        # Timestamps for cooldown enforcement
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

    async def run_decision_cycle(self) -> None:
        """
        Run one full decision cycle.

        Called every ~5 seconds by CognitiveService.
        Builds context → asks behaviors for decisions → executes the first one.
        """
        context = self._build_context()

        for behavior in self.behaviors:
            decision = await behavior.tick(context)
            if decision:
                await self._execute_decision(decision)
                break  # Only one action per tick

    def _build_context(self) -> dict:
        """
        Build the context object passed to every behavior.

        Returns:
            dict: Everything a behavior needs to make a smart decision
        """
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,                    # ← changed
            "features": getattr(self.tracker, "features", {}),
            "last_autonomous_speech_time": self.last_autonomous_speech_time,
            "last_user_input_response_time": self.last_user_input_response_time,
        }

    async def _execute_decision(self, decision: dict) -> None:
        """
        Execute the winning decision from a behavior.

        Creates the appropriate event and publishes it to the bus.
        Updates internal timers for cooldowns.

        Args:
            decision: Dict returned by a behavior's .tick() method
        """
        now = datetime.now(timezone.utc)

        if decision["type"] == "monologue":
            topic = decision["topic"]
            prompt = f"Monologue about {topic}, in character as Qubit."

            event = MonologueEvent(
                type="monologue_prompt",
                user="system",
                timestamp=now.isoformat(),
                data={"user": "system", "topic": topic, "prompt": prompt},
                prompt=prompt
            )
            await self.event_bus.publish(event)
            self.last_autonomous_speech_time = now

        elif decision["type"] == "response":
            best = decision["best_message"]
            event = ResponsePromptEvent(
                type="response_prompt",
                timestamp=now.isoformat(),
                data={"user": "viewer", "source": best["source"]},
                user="viewer",
                source=best["source"],
                prompt=best["text"]
            )
            await self.event_bus.publish(event)
            self.last_user_input_response_time = now

            # Clean up using the new queue
            self.tracker.queue.remove(best)   # ← fixed

    async def trigger_initial_monologue(self) -> None:
        """
        Special one-time monologue on bot start (welcome message).
        Called from CognitiveService._on_bot_start().
        """
        await self._execute_decision({
            "type": "monologue",
            "topic": "welcome to the stream",
            "reason": "bot_start"
        })