"""
FastAPI router for reading and writing the streamer profile JSON.

The profile lives in the pipeline repo at src/data/streamer_profile.json.
The pipeline root is resolved from the PIPELINE_ROOT environment variable,
defaulting to the directory one level above the frontend repo (standard
sibling-repo layout: qubit-frontend/ and qubit-pipeline/ sit in the same
parent directory).
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

profile_router = APIRouter(prefix="/profile")

_FRONTEND_ROOT = Path(__file__).parent
_DEFAULT_PIPELINE_ROOT = _FRONTEND_ROOT.parent / "qubit-pipeline-2026"
_PIPELINE_ROOT = Path(os.environ.get("PIPELINE_ROOT", str(_DEFAULT_PIPELINE_ROOT)))
_PROFILE_PATH = _PIPELINE_ROOT / "src" / "data" / "streamer_profile.json"

_EMPTY_PROFILE = {
    "streamer_name": "",
    "topics": [],
    "references": [],
    "avoid": [],
}


class StreamerProfilePayload(BaseModel):
    streamer_name: str = ""
    topics: list[str] = []
    references: list[str] = []
    avoid: list[str] = []


@profile_router.get("")
async def get_profile() -> JSONResponse:
    """Return the current streamer profile, or an empty template if none exists."""
    if not _PROFILE_PATH.exists():
        return JSONResponse(_EMPTY_PROFILE)
    try:
        data = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        # Normalise — ensure all expected keys are present
        for key, default in _EMPTY_PROFILE.items():
            data.setdefault(key, default)
        return JSONResponse(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read profile: {exc}")


@profile_router.post("")
async def save_profile(payload: StreamerProfilePayload) -> JSONResponse:
    """
    Write the profile to disk. Strips blank lines from all list fields.
    The pipeline's TopicSelector picks up the change on the next restart;
    a running instance needs a reload (see /profile/reload).
    """
    data = {
        "streamer_name": payload.streamer_name.strip(),
        "topics":     [t.strip() for t in payload.topics     if t.strip()],
        "references": [r.strip() for r in payload.references if r.strip()],
        "avoid":      [a.strip() for a in payload.avoid      if a.strip()],
    }
    try:
        _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PROFILE_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write profile: {exc}")

    return JSONResponse({"ok": True, "path": str(_PROFILE_PATH)})