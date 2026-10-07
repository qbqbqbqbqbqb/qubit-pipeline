"""
DecisionEngine - runs one cognitive decision cycle: build context, collect
proposals, pick a winner, execute it.

Scoring/priority logic lives in ProposalArbiter, idle-monologue quota
tracking lives in IdleQuotaTracker, and turning a winning proposal into a
published event lives in DecisionExecutor — this class just wires them
together and owns the per-cycle sequencing.
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
from src.utils.log_utils import get_logger


class DecisionEngine:
    def __init__(self, tracker: ActivityTracker, event_bus):
        self.tracker = tracker
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
        self.tracker.apply_time_decay()

        idle_catchup = self.idle_quota.is_under_quota()
        context = self._build_context(idle_catchup)
        self._log_cycle_start(context)

        proposals = await self._collect_proposals(context)
        if not proposals:
            return

        winner = self.arbiter.select_winner(
            proposals,
            extra_bonus_by_reason={"idle_monologue": self.idle_quota.catchup_bonus()},
        )
        self._log_winner(winner)
        await self._execute_decision(winner)

    async def _collect_proposals(self, context: dict) -> list[dict]:
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
        now = datetime.now(timezone.utc)
        last_autonomous = self.executor.last_autonomous_speech_time
        last_response = self.executor.last_user_input_response_time
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,
            "pending_events": self.tracker.peek_pending_events(),
            "features": getattr(self.tracker, "features", {}),
            # Tells IdleMonologueBehavior to bypass its own cooldown/spark
            # gates this cycle — see IdleQuotaTracker's docstring for why.
            "idle_quota_catchup": idle_catchup,
            "last_autonomous_speech_time": last_autonomous,
            "last_user_input_response_time": last_response,
            "time_since_last_autonomous": (now - last_autonomous).total_seconds(),
            "time_since_last_user_response": (now - last_response).total_seconds(),
            # Peeked, not consumed: if this command doesn't end up winning
            # the cycle (e.g. a raid arrives the same moment), it must still
            # be here to compete again next cycle instead of being lost.
            "frontend_command": self.tracker.peek_frontend_command(),
        }

    async def _execute_decision(self, decision: dict) -> None:
        now = datetime.now(timezone.utc)
        source_behavior = decision.pop("_source_behavior", None)
        reason = decision.get("reason", "")

        await self.executor.execute(decision, now)

        if source_behavior is not None:
            source_behavior.last_triggered = now

        self.idle_quota.record(reason)

    def _log_cycle_start(self, context: dict) -> None:
        if not self.logger.isEnabledFor(logging.INFO):
            return
        pending_chat = len(getattr(self.tracker.queue, "messages", []))
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