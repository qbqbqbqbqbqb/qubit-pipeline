import random
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.frontend_monologue import FrontendTriggeredMonologueBehavior
from src.qubit.core.events import MonologueEvent, ResponsePromptEvent
from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.utils.log_utils import get_logger


class DecisionEngine:
    """
    Pure decision logic for the Cognitive layer.

    This is the component that actually chooses what the bot does next.

    Responsibilities:
    - Build a context snapshot from the ActivityTracker (scores, queue, features, timers)
    - Execute all registered behaviours in a defined order
    - Select and execute at most one winning behaviour per decision cycle
    - Publish the resulting high-level event (ResponsePromptEvent or MonologueEvent)

    Strict constraints:
    - No prompt assembly
    - No LLM calls
    - No direct output or TTS
    - All "intelligence" is delegated to individual Behaviour implementations

    The 5-second cycle is driven by the CognitiveOrchestrator.
    """

    def __init__(self, tracker: ActivityTracker, event_bus):
        """
        Initialize the decision engine.

        Args:
            tracker: ActivityTracker instance that holds score + priority queue
            event_bus: The central event bus used to publish final decisions
        """
        self.tracker = tracker
        self.logger = get_logger("DecisionEngine")
        self.event_bus = event_bus
        self.behaviors = [IdleMonologueBehavior(), ChatResponseBehavior(), FrontendTriggeredMonologueBehavior()]
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

    async def run_decision_cycle(self) -> None:
        """
        Execute one decision cycle (called every 5s by the orchestrator).

        Process:
        1. Snapshot current state into a context dict from the tracker.
        2. Iterate behaviours in priority order (Idle, ChatResponse, FrontendMonologue).
        3. The first behaviour that returns a non-None decision wins.
        4. Execute that decision (publish event + update cooldown timers).
        5. Stop — only one action per cycle is allowed.

        This "at most one winner" rule prevents conflicting actions (e.g. monologue + response at the same time).
        """
        context = self._build_context()
        self.logger.info(f"[DecisionEngine] Cycle | activity={context['activity_score']:.2f} | "
                        f"pending={len(getattr(self.tracker.queue, 'messages', []))} | "
                        f"last_mono={(datetime.now(timezone.utc) - self.last_autonomous_speech_time).total_seconds():.0f}s")

        for behavior in self.behaviors:
            decision = await behavior.tick(context)
            if decision:
                await self._execute_decision(decision)
                break

    def _build_context(self) -> dict:
        """
        Construct the rich context snapshot passed to every Behaviour.tick().

        The context contains everything behaviours need to make informed decisions:
        - Current activity score
        - The priority queue of pending inputs
        - Feature flags (monologue, stt, etc.)
        - Cooldown timers
        - Any pending frontend command
        """
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,
            "features": getattr(self.tracker, "features", {}),
            "last_autonomous_speech_time": self.last_autonomous_speech_time,
            "last_user_input_response_time": self.last_user_input_response_time,
            "frontend_command": self.tracker.consume_frontend_command()
        }

    async def _execute_decision(self, decision: dict) -> None:
        """
        Execute the single winning decision returned by a Behaviour.

        Supported decision types:
        - "response" → publish ResponsePromptEvent (triggers Generation)
        - "monologue" → publish MonologueEvent (triggers autonomous speech)

        Also updates the last_*_time trackers used for cooldown logic in behaviours.
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

            self.tracker.queue.remove(best)