"""
<summary>
DecisionExecutor — turns a winning proposal into a published event, clears
the state that decision consumed, and owns the timers that behaviours read
via context to implement their cooldowns.
</summary>
<remarks>
The timers live here rather than on DecisionEngine because this is the single
place that knows when an execution happened, making it the authoritative source
of truth for both last_autonomous_speech_time and last_user_input_response_time.
</remarks>
"""

from datetime import datetime, timezone

from src.qubit.core.events import MonologueEvent, ResponsePromptEvent


class DecisionExecutor:
    """
    <summary>
    Executes the winning decision from each cognitive cycle by publishing the
    appropriate event and updating shared timers and queue state.
    </summary>
    """

    def __init__(self, tracker, event_bus):
        """
        <summary>Initialise the executor with references to the tracker and event bus.</summary>
        <param name="tracker">The ActivityTracker for queue and frontend-command mutations.</param>
        <param name="event_bus">The EventBus to publish outcome events onto.</param>
        """
        self.tracker = tracker
        self.event_bus = event_bus
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)

    async def execute(self, decision: dict, now: datetime) -> None:
        """
        <summary>Dispatch the winning proposal to the appropriate execution path.</summary>
        <param name="decision">The winning proposal dict (type, reason, and payload fields).</param>
        <param name="now">The timestamp for this cycle, used in emitted events and timers.</param>
        """
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
        """
        <summary>Publish a MonologueEvent for an autonomous or frontend-triggered speech prompt.</summary>
        <param name="decision">The monologue proposal dict containing 'prompt' and 'label'.</param>
        <param name="now">Current cycle timestamp.</param>
        """
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
        """
        <summary>Publish a ResponsePromptEvent for the best pending user message and remove it from the queue.</summary>
        <param name="decision">The response proposal dict containing 'best_message'.</param>
        <param name="now">Current cycle timestamp.</param>
        """
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
        <summary>
        Publish a MonologueEvent for a community event reaction (raid, gift, follow)
        and remove the consumed events from the queue.
        </summary>
        <remarks>
        Reuses MonologueEvent because a raid/gift/follow reaction is Qubit speaking
        on her own initiative about something that just happened — the same shape as
        an idle monologue with a forced topic. Deliberately does not touch
        last_autonomous_speech_time or last_user_input_response_time, since a
        community-event reaction is its own category and should not reset either timer.
        </remarks>
        <param name="decision">The community_event proposal dict containing 'topic' and 'events'.</param>
        <param name="now">Current cycle timestamp.</param>
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
