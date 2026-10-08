"""
CommunityEventQueue - pending raid/gift/follow reactions.

Owned by ActivityTracker. Deliberately separate from the chat/STT
InputPriorityQueue — these don't have meaningful "text" and shouldn't be
scored by chat quality heuristics. CommunityEventBehavior collates
whatever is pending each cycle; see behaviours/community.py.

Each event is assigned a uuid on arrival and stored in an OrderedDict
keyed by that id. Removal is by id (O(1)), so it is unaffected by any
mutation of the event dict between peek and remove.
"""

from collections import OrderedDict
from uuid import uuid4


class CommunityEventQueue:
    def __init__(self):
        self._pending: OrderedDict[str, dict] = OrderedDict()

    def add(self, detail: dict) -> None:
        """Assign a stable id to the event and enqueue it."""
        event_id = str(uuid4())
        detail["_id"] = event_id
        self._pending[event_id] = detail

    def peek(self) -> list[dict]:
        """Non-destructive read for building context — a losing proposal must not lose these."""
        return list(self._pending.values())

    def remove(self, events: list[dict]) -> None:
        """Remove exactly the given events by their assigned id."""
        for e in events:
            event_id = e.get("_id")
            if event_id and event_id in self._pending:
                del self._pending[event_id]
