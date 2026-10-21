"""
Shared pure helpers for input processing.
"""

from datetime import datetime, timedelta, timezone
from src.qubit.utils.log_utils import get_logger

logger = get_logger(__name__)


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