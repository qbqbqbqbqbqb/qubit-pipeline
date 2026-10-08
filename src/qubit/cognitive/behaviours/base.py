from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Behavior(ABC):
    """
    Abstract base for a pluggable decision strategy in the cognitive layer.

    Contract (scored proposal model):
    - Receives a context dict built by DecisionEngine._build_context().
    - Returns either None (no proposal) or a scored proposal dict:
        {
            "type": "response" | "monologue",
            "score": float,                 # normalized ~0.0-1.0: how much THIS
                                             # behavior wants to act, on its own
                                             # internal scale (see its SCORE_FLOOR/
                                             # SCORE_CEILING for how it gets there).
                                             # Priority BETWEEN behaviors is decided
                                             # separately, by DecisionEngine.
                                             # BEHAVIOR_WEIGHTS — a score of 1.0 from
                                             # two different behaviors is not meant
                                             # to be treated as equally urgent unless
                                             # their weights also match.
            "reason": str,
            "best_message": dict | None,    # only for "response"
            "prompt": str | None,           # only for "monologue" — full LLM instruction
            "label": str | None,            # only for "monologue" — human-readable log label
        }
    - Stateful only in two ways, both owned by DecisionEngine rather than the
      behavior itself:
        * `enabled`        — kill-switch DecisionEngine checks before calling tick().
        * `last_triggered` — set by DecisionEngine after this behavior's proposal
                              wins a cycle. Useful if a future behavior wants its
                              own cooldown instead of relying on the shared timers
                              in ActivityTracker/context.
    - Everything else a behavior needs (timers, features, queue state) comes from
      context, not from instance state — behaviors don't mutate their own state
      during tick().

    Adding a new behavior: subclass this, implement tick(), add an instance to
    DecisionEngine.behaviors, and give it an entry in DecisionEngine.BEHAVIOR_WEIGHTS.
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.last_triggered: datetime = datetime.now(timezone.utc)

    @abstractmethod
    async def tick(self, context: dict) -> dict | None:
        """
        Evaluate context and return a scored proposal or None.

        The returned dict MUST contain at minimum: "type", "score", "reason".
        Optional keys: "best_message", "topic" depending on type.
        """
        raise NotImplementedError