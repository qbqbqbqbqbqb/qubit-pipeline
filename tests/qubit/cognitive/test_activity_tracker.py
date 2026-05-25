import pytest
from unittest.mock import MagicMock
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.core.events import Event


class TestActivityTracker:
    @pytest.fixture
    def tracker(self):
        return ActivityTracker()

    @pytest.fixture
    def features(self):
        return {
            "stt": True,
            "monologue": True,
            "twitch": True,
        }

    def test_handle_input_ignores_short_text(self, tracker, features):
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "hi"}

        # Should not crash and should not add to queue
        import asyncio
        asyncio.run(tracker.handle_input(event, features))
        assert len(tracker.queue.messages) == 0

    def test_handle_input_increases_activity_score(self, tracker, features):
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "this is a proper message with some length"}

        import asyncio
        asyncio.run(tracker.handle_input(event, features))

        assert tracker.activity_score > 0
        assert len(tracker.queue.messages) == 1

    def test_stt_gets_higher_weight(self, tracker, features):
        event = MagicMock()
        event.type = "stt_processed"
        event.data = {"text": "spoken words from user"}

        initial = tracker.activity_score
        import asyncio
        asyncio.run(tracker.handle_input(event, features))

        assert tracker.activity_score > initial + 4  # high weight for STT

    def test_monologue_disabled_reduces_weight(self, tracker):
        features = {"stt": True, "monologue": False}
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "a normal chat message here"}

        import asyncio
        asyncio.run(tracker.handle_input(event, features))

        # weight should be reduced
        assert tracker.activity_score < 2.0
