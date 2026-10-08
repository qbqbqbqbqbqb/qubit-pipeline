"""
DecisionExecutor - turns a winning proposal into a published event, clears
whatever state that decision consumed, and owns the "when did we last
speak" timers that ChatResponseBehavior/IdleMonologueBehavior read via
context.

Split out from DecisionEngine because this changes for different reasons
than scoring does: you'll retune weights/tiers often as you balance the
bot's feel, but you'll rarely touch how a MonologueEvent gets constructed.
The timers live here rather than on DecisionEngine because this is the one
place that actually knows when an execution happened — single source of
truth instead of a value written in one file and read in another.
"""

from datetime import datetime, timezone

from src.qubit.core.events import MonologueEvent, ResponsePromptEvent


class DecisionExecutor:
    def __init__(self, tracker, event_bus):
        self.tracker = tracker
        self.event_bus = event_bus
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

    async def execute(self, decision: dict, now: datetime) -> None:
        reason = decision.get("reason", "")

        if decision["type"] == "monologue":
            await self._execute_monologue(decision, now)
            if reason.startswith("frontend_"):
                self.tracker.consume_frontend_command()
        elif decision["type"] == "response":
            await self._execute_response(decision, now)
        elif decision["type"] == "community_event":
            await self._execute_community_event(decision, now)

    async def _execute_monologue(self, decision: dict, now: datetime) -> None:
        prompt = decision["prompt"]
        label = decision.get("label", "unknown")

        event = MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=now.isoformat(),
            data={"user": "system", "label": label, "prompt": prompt},
            prompt=prompt,
        )
        await self.event_bus.publish(event)
        self.last_autonomous_speech_time = now

    async def _execute_response(self, decision: dict, now: datetime) -> None:
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

    async def _execute_community_event(self, decision: dict, now: datetime) -> None:
        """
        Reuses MonologueEvent — a raid/gift/follow reaction is Qubit
        speaking on her own initiative about something that just happened,
        the same shape as an idle monologue with a forced topic. If you want
        these distinguishable downstream (different TTS emphasis, a
        dedicated overlay animation), add a real CommunityEventPromptEvent
        to core/events.py and swap it in here.
        """
        topic = decision["topic"]
        prompt = f"React to {topic}, in character as Qubit."

        event = MonologueEvent(
            type="monologue_prompt",
            user="system",
            timestamp=now.isoformat(),
            data={"user": "system", "topic": topic, "prompt": prompt, "kind": "community_event"},
            prompt=prompt,
        )
        await self.event_bus.publish(event)

        self.tracker.remove_pending_events(decision["events"])
        # Deliberately NOT touching last_autonomous_speech_time or
        # last_user_input_response_time — a community-event reaction is its
        # own rare category and shouldn't reset either the idle or chat
        # cooldown.