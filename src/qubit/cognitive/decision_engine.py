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
    Pure decision logic for the Cognitive layer (scored proposal model).

    Every 5s cycle:
    1. Build rich context snapshot.
    2. Ask EVERY registered behavior for a scored proposal (or None).
    3. Select the single highest-scoring proposal.
    4. Execute it (publish event + update timers).
    5. Only one action per cycle.

    Key properties (designed for your requirements):
    - STT responses receive massive score boosts inside ChatResponseBehavior → they win at ANY activity level.
    - At low activity: both IdleMonologue and responses get high willingness scores → natural mix.
    - At high activity: ChatResponse becomes selective (only strong STT + high-quality chat survive), while Idle still has a chance for occasional autonomous color.
    - Adding new behaviors (raids, emotes, alerts, etc.) is safe and automatic.
    """

    def __init__(self, tracker: ActivityTracker, event_bus):
        self.tracker = tracker
        self.logger = get_logger("DecisionEngine")
        self.event_bus = event_bus
        self.behaviors = [
            IdleMonologueBehavior(),
            ChatResponseBehavior(),
            FrontendTriggeredMonologueBehavior(),
        ]
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

    async def run_decision_cycle(self) -> None:
        context = self._build_context()

        pending = len(getattr(self.tracker.queue, "messages", []))
        self.logger.info(
            f"[DecisionEngine] Cycle | activity={context['activity_score']:.2f} | "
            f"pending={pending} | "
            f"last_mono={(datetime.now(timezone.utc) - self.last_autonomous_speech_time).total_seconds():.0f}s"
        )

        proposals: list[dict] = []
        for behavior in self.behaviors:
            proposal = await behavior.tick(context)
            if proposal:
                proposals.append(proposal)

        if not proposals:
            return

        # STT hard priority tie-breaker: any proposal whose best_message is STT wins ties
        def proposal_key(p: dict) -> float:
            score = p.get("score", 0.0)
            best = p.get("best_message")
            if best and best.get("source") == "user_input_stt":
                score += 10.0  # absolute dominance for live streamer voice
            return score

        winner = max(proposals, key=proposal_key)

        self.logger.info(
            f"[DecisionEngine] WINNER: {winner.get('reason')} (score={winner.get('score'):.3f})"
        )

        await self._execute_decision(winner)

    def _build_context(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,
            "features": getattr(self.tracker, "features", {}),
            "last_autonomous_speech_time": self.last_autonomous_speech_time,
            "last_user_input_response_time": self.last_user_input_response_time,
            "time_since_last_autonomous": (now - self.last_autonomous_speech_time).total_seconds(),
            "time_since_last_user_response": (now - self.last_user_input_response_time).total_seconds(),
            "frontend_command": self.tracker.consume_frontend_command(),
        }

    async def _execute_decision(self, decision: dict) -> None:
        now = datetime.now(timezone.utc)

        if decision["type"] == "monologue":
            topic = decision["topic"]
            prompt = f"Monologue about {topic}, in character as Qubit."

            event = MonologueEvent(
                type="monologue_prompt",
                user="system",
                timestamp=now.isoformat(),
                data={"user": "system", "topic": topic, "prompt": prompt},
                prompt=prompt,
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
                prompt=best["text"],
            )
            await self.event_bus.publish(event)
            self.last_user_input_response_time = now
            self.tracker.queue.remove(best)