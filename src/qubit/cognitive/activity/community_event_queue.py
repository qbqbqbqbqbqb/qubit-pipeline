"""
<summary>
CommunityEventQueue — pending raid/gift/follow reaction queue.
Owned by ActivityTracker.
</summary>
<remarks>
Separate from the chat/STT InputPriorityQueue because community events have no
meaningful text and should not be scored by chat quality heuristics.
CommunityEventBehavior collates whatever is pending each cycle.

Each event is assigned a UUID on arrival and stored in an OrderedDict keyed by
that id. Removal is O(1) by id and is unaffected by any mutation of the event
dict between peek and remove.
</remarks>
"""

from collections import OrderedDict
from uuid import uuid4


class CommunityEventQueue:
    """
    <summary>
    Ordered queue of pending community events (raids, subscriptions, follows).
    Supports non-destructive peeking and removal by stable id.
    </summary>
    """

    def __init__(self):
        self._pending: OrderedDict[str, dict] = OrderedDict()

    def add(self, detail: dict) -> None:
        """
        <summary>Assign a stable id to the event and enqueue it.</summary>
        <param name="detail">Event detail dict produced by EventAdapter.extract_event_detail().</param>
        """
        event_id = str(uuid4())
        detail["_id"] = event_id
        self._pending[event_id] = detail

    def peek(self) -> list[dict]:
        """
        <summary>
        Non-destructive read of all pending events. A losing proposal must not consume these.
        </summary>
        <returns>A list of all currently queued event dicts.</returns>
        """
        return list(self._pending.values())

    def remove(self, events: list[dict]) -> None:
        """
        <summary>Remove exactly the given events by their assigned id.</summary>
        <param name="events">List of event dicts to remove (each must contain '_id').</param>
        """
        for e in events:
            event_id = e.get("_id")
            if event_id and event_id in self._pending:
                del self._pending[event_id]
