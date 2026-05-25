"""
Shared fixtures for all cognitive tests.

These fixtures help keep cognitive tests consistent, well-isolated, and aligned
with the mocking strategy in tests/AGENTS.md.

Usage:
    def test_something(mock_cognitive_context, mock_heavy_stack):
        ...
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.cognitive.decision_engine import DecisionEngine
from src.qubit.cognitive.priority_queue import InputPriorityQueue


@pytest.fixture
def mock_cognitive_context():
    """A realistic base context dict used by behaviours and DecisionEngine."""
    now = datetime.now(timezone.utc)
    queue = MagicMock(spec=InputPriorityQueue)
    queue.get_best.return_value = None
    queue.messages = []

    return {
        "activity_score": 0.0,
        "queue": queue,
        "features": {
            "monologue": True,
            "stt": True,
            "twitch": True,
            "response": True,
        },
        "last_autonomous_speech_time": now - timedelta(seconds=120),
        "last_user_input_response_time": now - timedelta(seconds=60),
        "frontend_command": None,
    }


@pytest.fixture
def cognitive_tracker():
    """A real ActivityTracker instance (lightweight, no heavy deps)."""
    return ActivityTracker()


@pytest.fixture
def cognitive_engine(cognitive_tracker, mock_heavy_stack):
    """
    A DecisionEngine with real tracker but mocked event bus and behaviors.

    Use this when you want to test DecisionEngine logic in isolation
    while still having a functional PriorityQueue.
    """
    mock_bus = AsyncMock()
    engine = DecisionEngine(cognitive_tracker, mock_bus)

    # Replace behaviors with mocks for controlled testing
    for behavior in engine.behaviors:
        behavior.tick = AsyncMock(return_value=None)

    return engine


@pytest.fixture
def seeded_priority_queue():
    """A PriorityQueue pre-seeded with some messages for testing."""
    q = InputPriorityQueue(maxlen=20)
    q.add("hello there", "user_input_chat_message", {"type": "chat"})
    q.add("this is a question?", "user_input_stt", {"type": "stt"})
    q.add("@qubit important thing", "user_input_chat_message", {"type": "chat"})
    return q
