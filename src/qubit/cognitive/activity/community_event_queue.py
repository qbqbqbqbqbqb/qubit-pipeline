"""
CommunityEventQueue - pending raid/gift/follow reactions.

Owned by ActivityTracker. Deliberately separate from the chat/STT
InputPriorityQueue — these don't have meaningful "text" and shouldn't be
scored by chat quality heuristics. CommunityEventBehavior collates
whatever is pending each cycle; see behaviours/community_event.py.
"""


class CommunityEventQueue:
    def __init__(self):
        self._pending: list[dict] = []

    def add(self, detail: dict) -> None:
        self._pending.append(detail)

    def peek(self) -> list[dict]:
        """Non-destructive read for building context — a losing proposal must not lose these."""
        return list(self._pending)

    def remove(self, events: list[dict]) -> None:
        """Remove exactly the given events (by equality), e.g. after they've been acknowledged."""
        for e in events:
            if e in self._pending:
                self._pending.remove(e)