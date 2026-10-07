"""
DecisionEngine - selects one action per cognitive cycle from scored behavior proposals.

LAYER: Cognitive

Every cycle:
1. Apply time-based activity decay (independent of new input).
2. Build a context snapshot from ActivityTracker.
3. Ask every enabled behavior for a scored proposal (or None).
4. Weight each proposal by BEHAVIOR_WEIGHTS, apply the idle-monologue
   quota catch-up bonus if under target, then apply the priority-tier bonus.
5. Execute the single winner (publish event, update timers, clear whatever
   state that decision consumed, record it toward the quota ratio).
"""

import logging
from collections import deque
from datetime import datetime, timezone

from src.qubit.cognitive.behaviours.community import CommunityEventBehavior
from src.qubit.cognitive.behaviours.frontend_monologue import FrontendTriggeredMonologueBehavior
from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.core.events import MonologueEvent, ResponsePromptEvent
from src.utils.log_utils import get_logger


class DecisionEngine:
    """
    Pure decision logic for the Cognitive layer (scored proposal model).

    Each behavior returns a proposal score normalized to roughly 0-1 — "how
    much do I want this, on my own internal scale." BEHAVIOR_WEIGHTS is the
    single place that decides how much a maxed-out proposal from one
    behavior matters relative to another.

    On top of weights, a proposal can set "priority_tier" (default 0). Each
    tier point adds PRIORITY_TIER_BONUS, which dwarfs any realistic weighted
    score — so tiers decide outright priority classes; weights only matter
    for tie-breaking within a tier.
        tier 0: chat_response (non-STT), idle_monologue, frontend_*
        tier 1: chat_response when the winning message is live STT
        tier 2: community_event (raids/gifts) — always wins, even over STT
    """

    BEHAVIOR_WEIGHTS: dict[str, float] = {
        "chat_response": 1.0,
        "frontend_start": 0.75,
        "frontend_random_fact": 0.75,
        "idle_monologue": 0.4,
        "community_event": 1.0,
    }
    DEFAULT_BEHAVIOR_WEIGHT = 0.4
    PRIORITY_TIER_BONUS = 10.0

    # --- idle monologue quota ---
    # While idle_monologue's actual win rate over the trailing window is
    # below IDLE_TARGET_SHARE, it enters "catch-up": its own random gates
    # (cooldown breach chance, high-activity spark chance) are bypassed, and
    # its proposal gets a decisive bonus that guarantees it wins the cycle.
    # Once the trailing window is back at/above target, catch-up switches
    # off and idle goes back to behaving exactly as its own curves define —
    # rare and organic. (A softer proportional correction was tried first
    # and verified NOT to reach target — see conversation — because idle's
    # own score ceiling at high activity is too far below chat's floor for
    # a bounded multiplier to close the gap; only a guaranteed win during
    # catch-up actually converges on the target share.)
    IDLE_TARGET_SHARE = 0.30
    RATIO_HISTORY_SIZE = 20
    RATIO_HISTORY_MIN_SAMPLES = 5
    IDLE_CATCHUP_BONUS = 5.0  # far exceeds any realistic tier-0 weighted score — guarantees the win

    def __init__(self, tracker: ActivityTracker, event_bus):
        self.tracker = tracker
        self.logger = get_logger("DecisionEngine")
        self.event_bus = event_bus
        self.behaviors: list = [
            IdleMonologueBehavior(),
            ChatResponseBehavior(),
            FrontendTriggeredMonologueBehavior(),
            CommunityEventBehavior(),
        ]
        self.last_autonomous_speech_time = datetime.now(timezone.utc)
        self.last_user_input_response_time = datetime.now(timezone.utc)
        self._decision_history: deque[str] = deque(maxlen=self.RATIO_HISTORY_SIZE)

    async def run_decision_cycle(self) -> None:
        self.tracker.apply_time_decay()

        idle_catchup = self._idle_under_quota()
        context = self._build_context(idle_catchup)
        self._log_cycle_start(context)

        proposals = await self._collect_proposals(context)
        if not proposals:
            return

        winner = self._select_winner(proposals, idle_catchup)
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

    def _select_winner(self, proposals: list[dict], idle_catchup: bool) -> dict:
        def proposal_key(p: dict) -> float:
            weight = self.BEHAVIOR_WEIGHTS.get(p.get("reason"), self.DEFAULT_BEHAVIOR_WEIGHT)
            score = p.get("score", 0.0) * weight
            score += p.get("priority_tier", 0) * self.PRIORITY_TIER_BONUS
            if idle_catchup and p.get("reason") == "idle_monologue":
                score += self.IDLE_CATCHUP_BONUS
            return score

        return max(proposals, key=proposal_key)

    def _idle_under_quota(self) -> bool:
        relevant = [d for d in self._decision_history if d in ("response", "monologue")]
        if len(relevant) < self.RATIO_HISTORY_MIN_SAMPLES:
            return False  # not enough history yet — let normal behavior run first
        share = relevant.count("monologue") / len(relevant)
        return share < self.IDLE_TARGET_SHARE

    def _build_context(self, idle_catchup: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "activity_score": self.tracker.activity_score,
            "queue": self.tracker.queue,
            "pending_events": self.tracker.peek_pending_events(),
            "features": getattr(self.tracker, "features", {}),
            # Tells IdleMonologueBehavior to bypass its own cooldown/spark
            # gates this cycle — see the class docstring above for why.
            "idle_quota_catchup": idle_catchup,
            "last_autonomous_speech_time": self.last_autonomous_speech_time,
            "last_user_input_response_time": self.last_user_input_response_time,
            "time_since_last_autonomous": (now - self.last_autonomous_speech_time).total_seconds(),
            "time_since_last_user_response": (now - self.last_user_input_response_time).total_seconds(),
            # Peeked, not consumed: if this command doesn't end up winning the
            # cycle (e.g. a raid arrives the same moment), it must still be
            # here to compete again next cycle instead of being silently lost.
            "frontend_command": self.tracker.peek_frontend_command(),
        }

    async def _execute_decision(self, decision: dict) -> None:
        now = datetime.now(timezone.utc)
        source_behavior = decision.pop("_source_behavior", None)
        reason = decision.get("reason", "")

        if decision["type"] == "monologue":
            await self._execute_monologue(decision, now)
            if reason.startswith("frontend_"):
                self.tracker.consume_frontend_command()
        elif decision["type"] == "response":
            await self._execute_response(decision, now)
        elif decision["type"] == "community_event":
            await self._execute_community_event(decision, now)

        if source_behavior is not None:
            source_behavior.last_triggered = now

        self._record_decision(reason)

    def _record_decision(self, reason: str) -> None:
        # Only chat_response vs idle_monologue feed the fairness ratio —
        # frontend commands are deliberate operator overrides and community
        # events are rare reactions; neither belongs in an emergent
        # "how much does she talk on her own vs. respond" measurement.
        if reason == "chat_response":
            self._decision_history.append("response")
        elif reason == "idle_monologue":
            self._decision_history.append("monologue")

    async def _execute_monologue(self, decision: dict, now: datetime) -> None:
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
        Reuses MonologueEvent — a raid/gift reaction is Qubit speaking on her
        own initiative about something that just happened, the same shape as
        an idle monologue with a forced topic. If you want these distinguishable
        downstream (different TTS emphasis, a dedicated overlay animation),
        add a real CommunityEventPromptEvent to core/events.py and swap it in
        here — I don't have that file in front of me to add it myself.
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
        # last_user_input_response_time — a raid/gift reaction is its own
        # rare category and shouldn't reset either the idle or chat cooldown.

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
            (datetime.now(timezone.utc) - self.last_autonomous_speech_time).total_seconds(),
        )

    def _log_winner(self, winner: dict) -> None:
        if not self.logger.isEnabledFor(logging.INFO):
            return
        self.logger.info(
            "[DecisionEngine] WINNER: %s (score=%.3f)",
            winner.get("reason"),
            winner.get("score", 0.0),
        )