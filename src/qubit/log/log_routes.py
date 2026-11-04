"""
FastAPI router that streams the chat training log to the control panel.

The log lives in the pipeline repo at logs/chat_training.jsonl, written by
ChatLogger. The PIPELINE_ROOT resolution follows the same pattern as
profile_routes.py: PIPELINE_ROOT env var, defaulting to the sibling repo.

Two endpoints:

  GET /log/chat
    Server-Sent Events stream. Tails the JSONL file from the last N lines on
    connect, then streams new lines as they are appended. The browser EventSource
    API reconnects automatically if the connection drops.

  GET /log/chat/snapshot
    Returns the last N lines as a JSON array. Used by the frontend on page
    load to populate the panel without waiting for new events.
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

log_router = APIRouter(prefix="/log")

_FRONTEND_ROOT = Path(__file__).parent
_DEFAULT_PIPELINE_ROOT = _FRONTEND_ROOT.parent / "qubit-pipeline-2026"
_PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", str(_DEFAULT_PIPELINE_ROOT)))
_LOG_PATH = _PIPELINE_ROOT / "logs" / "chat_training.jsonl"

# How many lines to send on initial connect / snapshot request
_TAIL_LINES = 100
# How often to poll for new content (seconds)
_POLL_INTERVAL = 1.0


def _tail(path: Path, n: int) -> list[dict]:
    """Return the last n parsed JSON lines from path, or [] if it doesn't exist."""
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        tail = lines[-n:] if len(lines) > n else lines
        result = []
        for line in tail:
            line = line.strip()
            if line:
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return result
    except OSError:
        return []


@log_router.get("/chat/snapshot")
async def chat_log_snapshot() -> JSONResponse:
    """Return the last _TAIL_LINES entries as a JSON array."""
    return JSONResponse(_tail(_LOG_PATH, _TAIL_LINES))


@log_router.get("/chat")
async def chat_log_stream() -> StreamingResponse:
    """
    Server-Sent Events stream that tails the JSONL log.

    On connect: emits the last _TAIL_LINES lines as individual events.
    Ongoing:    polls for new lines appended since the last read position
                and emits each one as an SSE event.
    """
    async def generate():
        # Seed with existing tail
        initial = _tail(_LOG_PATH, _TAIL_LINES)
        for entry in initial:
            yield f"data: {json.dumps(entry)}\n\n"

        # Track byte offset so we only read genuinely new content
        try:
            offset = _LOG_PATH.stat().st_size if _LOG_PATH.exists() else 0
        except OSError:
            offset = 0

        while True:
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                if not _LOG_PATH.exists():
                    continue
                size = _LOG_PATH.stat().st_size
                if size <= offset:
                    # File hasn't grown (or was truncated — reset)
                    if size < offset:
                        offset = size
                    continue
                with _LOG_PATH.open("r", encoding="utf-8") as f:
                    f.seek(offset)
                    new_content = f.read()
                offset = _LOG_PATH.stat().st_size
                for line in new_content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        yield f"data: {json.dumps(entry)}\n\n"
                    except json.JSONDecodeError:
                        pass
            except OSError:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if proxied
        },
    )