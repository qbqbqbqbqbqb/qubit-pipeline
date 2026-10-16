"""
<summary>
Shared pure helpers for input processing.
</summary>
<remarks>
Contains the only logic shared between multiple input processors:
  - Staleness checking based on event timestamp and max_age.
  - Forwarding events to the memory handler.

Both are intentionally free functions with no side effects beyond logging
and calling the provided memory_writer. This keeps individual processors
thin and obviously correct.
</remarks>
"""

from datetime import datetime, timedelta, timezone
from typing import Any


async def is_stale(event: Any, max_age: timedelta, logger: Any, context: str = "") -> bool:
    """
    <summary>Return True if the event is older than max_age.</summary>
    <remarks>
    The check is performed against the event's timestamp field, or against
    now() if the field is absent. A debug log is emitted when an event is
    considered stale.
    </remarks>
    <param name="event">The event to check (must have .timestamp or .data timestamp).</param>
    <param name="max_age">Maximum allowed age.</param>
    <param name="logger">Logger for the debug message.</param>
    <param name="context">Optional prefix for the log message (e.g. "monologue" or "chat").</param>
    <returns>True if the event should be dropped as stale.</returns>
    """
    ts = getattr(event, "timestamp", datetime.now(timezone.utc))
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)

    if datetime.now(timezone.utc) - ts > max_age:
        prefix = context or "unknown"
        logger.debug("[%s] Dropping stale message: %s", prefix, event.data.get("text", "")[:80])
        return True
    return False


async def forward_to_memory(event: Any, memory_writer: Any, logger: Any) -> None:
    """
    <summary>
    Forward the event to the memory writer if one is configured.
    Pure delegation with logging; no transformation is performed.
    </summary>
    <param name="event">The event to forward.</param>
    <param name="memory_writer">The MemoryWriter instance, or None.</param>
    <param name="logger">Logger for the info message.</param>
    """
    if memory_writer:
        logger.info("[forward_to_memory] Forwarding %s to memory", getattr(event, "type", "unknown"))
        await memory_writer.handle_event(event)
