"""
<summary>
Abstract base class for pluggable decision strategies in the cognitive layer.
</summary>
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Behavior(ABC):
    """
    <summary>
    Abstract base for a behaviour that participates in the scored proposal model.
    </summary>
    <remarks>
    Contract:
      - Receives a context dict built by DecisionEngine._build_context().
      - Returns None (no proposal) or a scored proposal dict with at minimum:
          type    : "response" | "monologue"
          score   : float — how much THIS behaviour wants to act, normalised ~0.0-1.0
                    on its own internal scale. Priority BETWEEN behaviours is decided
                    by ProposalArbiter.BEHAVIOR_WEIGHTS, not by this score alone.
          reason  : str
        Optional keys:
          best_message : dict | None  — only for "response" type
          prompt       : str | None   — only for "monologue" type
          label        : str | None   — only for "monologue" type; human-readable log label
      - Stateful only via two fields managed by DecisionEngine:
          enabled        — kill-switch checked before tick() is called.
          last_triggered — set after this behaviour's proposal wins a cycle.
      - Everything else a behaviour needs (timers, features, queue state) comes from
        context, not from instance state.

    Adding a new behaviour: subclass this, implement tick(), add an instance to
    DecisionEngine.behaviors, and give it an entry in ProposalArbiter.BEHAVIOR_WEIGHTS.
    </remarks>
    """

    def __init__(self, name: str):
        """
        <summary>Initialise the behaviour with a name and default state.</summary>
        <param name="name">Human-readable name used in logs.</param>
        """
        self.name = name
        self.enabled = True
        self.last_triggered: datetime = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: dict) -> dict | None:
        """
        <summary>
        Evaluate context and return a scored proposal or None.
        The returned dict must contain at minimum: 'type', 'score', 'reason'.
        </summary>
        <param name="context">The context dict from DecisionEngine._build_context().</param>
        <returns>A proposal dict, or None if this behaviour has nothing to propose.</returns>
        """
        raise NotImplementedError
