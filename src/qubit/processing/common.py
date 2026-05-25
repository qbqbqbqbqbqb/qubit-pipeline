"""
Shared pure helpers for input processing (private module).

These functions contain the only duplicated logic that used to live in both
InputHandler and AutonomousInputHandler:

- Staleness checking (based on event timestamp + max_age)
- Forwarding events to the memory handler (if present)

They are intentionally free functions with no side effects except logging
and calling the provided memory_writer. This makes the two processors
trivial and obviously correct while preserving 100% identical behavior.
"""

from datetime import datetime, timedelta, timezone
from typing import Any


async def is_stale(event: Any, max_age: timedelta, logger: Any, context: str = "") -> bool:
    """
    Return True if the event is older than max_age.

    The check is performed against the event's timestamp (or now if missing).
    A debug log is emitted when an event is considered stale.

    Parameters
    ----------
    event : Event
        The event to check (must have .timestamp or .data timestamp).
    max_age : timedelta
        Maximum allowed age.
    logger : logging.Logger
        Logger to use for the debug message.
    context : str
        Optional prefix for the log message (e.g. "monologue" or "chat").

    Returns
    -------
    bool
        True if the event should be dropped as stale.
    """
    ts = getattr(event, "timestamp", datetime.now(timezone.utc))
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)

    if datetime.now(timezone.utc) - ts > max_age:
        prefix = f"[{context}] " if context else ""
        logger.debug(f"{prefix}Dropping stale message: %s", event.data.get("text", "")[:80])
        return True
    return False


async def forward_to_memory(event: Any, memory_writer: Any, logger: Any) -> None:
    """
    Forward the event to the memory writer (MemoryWriter) if one is configured.

    This is a pure delegation with logging. No transformation is performed.
    """
    if memory_writer:
        logger.info("[forward_to_memory] Forwarding %s to memory", getattr(event, "type", "unknown"))
        await memory_writer.handle_event(event)
