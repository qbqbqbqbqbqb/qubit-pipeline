import pytest
from unittest.mock import MagicMock
import pytest_asyncio  # for async fixtures if needed
from src.qubit.cognitive.activity_tracker import ActivityTracker
from src.qubit.core.events import Event


@pytest.fixture
def features():
    return {
        "stt": True,
        "monologue": True,
        "twitch": True,
    }


class TestActivityTracker:
    @pytest.fixture
    def tracker(self):
        return ActivityTracker()

    @pytest.mark.asyncio
    async def test_handle_input_ignores_short_text(self, tracker, features, mock_heavy_stack):
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "hi"}

        await tracker.handle_input(event, features)
        assert len(tracker.queue.messages) == 0

    @pytest.mark.asyncio
    async def test_handle_input_increases_activity_score(self, tracker, features, mock_heavy_stack):
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "this is a proper message with some length"}

        await tracker.handle_input(event, features)

        assert tracker.activity_score > 0
        assert len(tracker.queue.messages) == 1

    @pytest.mark.asyncio
    async def test_stt_gets_higher_weight(self, tracker, features, mock_heavy_stack):
        event = MagicMock()
        event.type = "stt_processed"
        event.data = {"text": "spoken words from user"}

        initial = tracker.activity_score
        await tracker.handle_input(event, features)

        assert tracker.activity_score > initial + 4  # high weight for STT

    @pytest.mark.asyncio
    async def test_monologue_disabled_reduces_weight(self, tracker, mock_heavy_stack):
        features = {"stt": True, "monologue": False}
        event = MagicMock()
        event.type = "twitch_chat_processed"
        event.data = {"text": "a normal chat message here"}

        await tracker.handle_input(event, features)

        # weight should be reduced
        assert tracker.activity_score < 2.0
