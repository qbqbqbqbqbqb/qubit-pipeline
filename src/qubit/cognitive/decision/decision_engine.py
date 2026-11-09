"""
<summary>
DecisionEngine — runs one cognitive decision cycle: build context, collect
proposals from behaviours, pick a winner, and execute it.
</summary>
<remarks>
Scoring and priority logic lives in ProposalArbiter.
Idle-monologue quota tracking lives in IdleQuotaTracker.
Turning a winning proposal into a published event lives in DecisionExecutor.
This class wires them together and owns the per-cycle sequencing.

After each cycle a "decision_made" event is published on the bus so that
WebSocketServerService can forward it to the control-panel decision dashboard.
</remarks>
"""

import logging
from datetime import datetime, timezone

from src.qubit.cognitive.activity.activity_tracker import ActivityTracker
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.behaviours.community import CommunityEventBehavior
from src.qubit.cognitive.behaviours.frontend_monologue import FrontendTriggeredMonologueBehavior
from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.decision.decision_executor import DecisionExecutor
from src.qubit.cognitive.decision.idle_quota_tracker import IdleQuotaTracker
from src.qubit.cognitive.decision.proposal_arbiter import ProposalArbiter
from src.qubit.core.events import Event
from src.qubit.utils.log_utils import get_logger


class DecisionEngine:
    """
    <summary>
    Wires together the behaviour list, ProposalArbiter, IdleQuotaTracker, and
    DecisionExecutor to produce and execute one decision per cycle.
    </summary>
    """

    def __init__(self, tracker: ActivityTracker, event_bus):
        """
        <summary>Construct the engine and instantiate all collaborators.</summary>
        <param name="tracker">The ActivityTracker providing shared cognitive state.</param>
        <param name="event_bus">The EventBus used by DecisionExecutor to publish outcomes.</param>
        """
        self.tracker = tracker
        self.event_bus = event_bus
        self.logger = get_logger("DecisionEngine")
        self.behaviors: list = [
            IdleMonologueBehavior(),
            ChatResponseBehavior(),
            FrontendTriggeredMonologueBehavior(),
            CommunityEventBehavior(),
        ]
        self.arbiter = ProposalArbiter()
        self.idle_quota = IdleQuotaTracker()
        self.executor = DecisionExecutor(tracker, event_bus)

    async def run_decision_cycle(self) -> None:
        """
        <summary>
        Execute one full decision cycle: build context, collect proposals,
        select a winner via the arbiter, and execute it.
        </summary>
        """
        idle_catchup = self.idle_quota.is_under_quota()
        context = self._build_context(idle_catchup)
        self._log_cycle_start(context)

        proposals = await self._collect_proposals(context)
        if not proposals:
            return

        winner = self.arbiter.select_winner(
            proposals,
            extra_bonus_by_reason={"idle_monologue": self.idle_quota.catchup_bonus(idle_catchup)},
        )
        self._log_winner(winner)
        await self._execute_decision(winner, proposals, context)

    async def _collect_proposals(self, context: dict) -> list[dict]:
        """
        <summary>Tick each enabled behaviour and collect non-None proposals.</summary>
        <param name="context">The context dict for this cycle.</param>
        <returns>A list of proposal dicts, each tagged with its source behaviour.</returns>
        """
        proposals = []
        for behavior in self.behaviors:
            if not behavior.enabled:
                continue
            proposal = await behavior.tick(context)
            if proposal:
                proposal["_source_behavior"] = behavior
                proposals.append(proposal)
        return proposals

    def _build_context(self, idle_catchup: bool) -> dict:
        """
        <summary>Construct the context dict passed to all behaviours this cycle.</summary>
        <param name="idle_catchup">True when IdleQuotaTracker signals the idle share is under target.</param>
        <returns>A dict of all values behaviours read during tick().</returns>
        """
        now = datetime.now(timezone.utc)
        last_autonomous = self.executor.last_autonomous_speech_time
        last_response = self.executor.last_user_input_response_time
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,
            "pending_events": self.tracker.peek_pending_events(),
            "features": self.tracker.features,
            "idle_quota_catchup": idle_catchup,
            "last_autonomous_speech_time": last_autonomous,
            "last_user_input_response_time": last_response,
            "time_since_last_autonomous": (now - last_autonomous).total_seconds(),
            "time_since_last_user_response": (now - last_response).total_seconds(),
            "frontend_command": self.tracker.peek_frontend_command(),
        }

    async def _execute_decision(
        self, decision: dict, all_proposals: list[dict], context: dict
    ) -> None:
        """
        <summary>
        Execute the winning proposal, update the source behaviour's last_triggered,
        record the outcome in the quota tracker, and publish a decision_made event
        for the control-panel dashboard.
        </summary>
        <param name="decision">The winning proposal dict.</param>
        <param name="all_proposals">Every proposal from this cycle (used for the dashboard).</param>
        <param name="context">The context dict for this cycle (supplies activity and queue depth).</param>
        """
        now = datetime.now(timezone.utc)
        source_behavior = decision.pop("_source_behavior", None)
        reason = decision.get("reason", "")

        await self.executor.execute(decision, now)

        if source_behavior is not None:
            source_behavior.last_triggered = now

        self.idle_quota.record(reason)

        await self._publish_decision_event(decision, all_proposals, context, now)

    async def _publish_decision_event(
        self,
        winner: dict,
        all_proposals: list[dict],
        context: dict,
        now: datetime,
    ) -> None:
        """
        <summary>
        Publish a decision_made event on the bus. WebSocketServerService
        forwards this to the frontend as a decision_log message.
        </summary>
        """
        # Compute the composite score the arbiter actually used so the
        # dashboard can show the same number the engine acted on.
        idle_catchup = context.get("idle_quota_catchup", False)
        catchup_bonus = self.idle_quota.catchup_bonus(idle_catchup)

        def composite(p: dict) -> float:
            reason = p.get("reason", "")
            weight = self.arbiter.BEHAVIOR_WEIGHTS.get(reason, self.arbiter.DEFAULT_BEHAVIOR_WEIGHT)
            score = p.get("score", 0.0) * weight
            score += p.get("priority_tier", 0) * self.arbiter.PRIORITY_TIER_BONUS
            if reason == "idle_monologue":
                score += catchup_bonus
            return round(score, 4)

        # Snapshot proposals without the internal _source_behavior object
        # (not JSON-serialisable).
        proposal_summaries = [
            {
                "reason": p.get("reason", ""),
                "type": p.get("type", ""),
                "raw_score": round(p.get("score", 0.0), 4),
                "composite_score": composite(p),
                "priority_tier": p.get("priority_tier", 0),
            }
            for p in all_proposals
        ]

        pending_chat = len(getattr(context.get("queue"), "messages", []))
        pending_events = len(context.get("pending_events", []))

        # Compute trailing idle share for the dashboard ratio bar.
        idle_share = self.idle_quota.trailing_idle_share()

        event = Event(
            type="decision_made",
            timestamp=now.isoformat(),
            data={
                "timestamp": now.isoformat(),
                "winner": {
                    "reason": winner.get("reason", ""),
                    "type": winner.get("type", ""),
                    "composite_score": composite(winner),
                },
                "proposals": proposal_summaries,
                "activity_score": round(context.get("activity_score", 0.0), 3),
                "pending_chat": pending_chat,
                "pending_events": pending_events,
                "idle_catchup": idle_catchup,
                "idle_share": idle_share,
                "idle_target": IdleQuotaTracker.TARGET_SHARE,
            },
        )
        await self.event_bus.publish(event)

    def _log_cycle_start(self, context: dict) -> None:
        if not self.logger.isEnabledFor(logging.INFO):
            return
        pending_chat = len(getattr(context.get("queue"), "messages", []))
        pending_events = len(context.get("pending_events", []))
        self.logger.info(
            "[DecisionEngine] Cycle | activity=%.2f | pending_chat=%s | pending_events=%s | last_mono=%.0fs",
            context["activity_score"],
            pending_chat,
            pending_events,
            (datetime.now(timezone.utc) - self.executor.last_autonomous_speech_time).total_seconds(),
        )

    def _log_winner(self, winner: dict) -> None:
        if not self.logger.isEnabledFor(logging.INFO):
            return
        self.logger.info(
            "[DecisionEngine] WINNER: %s (score=%.3f)",
            winner.get("reason"),
            winner.get("score", 0.0),
        )