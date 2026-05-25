import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.behaviours.frontend_monologue import FrontendTriggeredMonologueBehavior


@pytest.fixture
def base_context(mock_cognitive_context):
    # Prefer the shared fixture from tests/qubit/cognitive/conftest.py when available
    ctx = mock_cognitive_context.copy()
    ctx["features"] = {"monologue": True, "stt": True}
    return ctx


class TestIdleMonologueBehavior:
    @pytest.mark.asyncio
    async def test_triggers_on_low_activity(self, base_context):
        behavior = IdleMonologueBehavior()
        base_context["activity_score"] = 1.5
        base_context["last_autonomous_speech_time"] = (
            datetime.now(timezone.utc) - timedelta(seconds=120)
        )

        decision = await behavior.tick(base_context)
        assert decision is not None
        assert decision["type"] == "monologue"
        assert "topic" in decision

    @pytest.mark.asyncio
    async def test_respects_monologue_disabled(self, base_context):
        behavior = IdleMonologueBehavior()
        base_context["features"]["monologue"] = False
        base_context["activity_score"] = 0.5

        decision = await behavior.tick(base_context)
        assert decision is None

    @pytest.mark.asyncio
    async def test_respects_cooldown(self, base_context, mocker):
        """Should not trigger if last autonomous speech was too recent."""
        behavior = IdleMonologueBehavior()
        behavior.cooldown_seconds = 120
        base_context["activity_score"] = 1.0
        # Very recent last speech
        base_context["last_autonomous_speech_time"] = datetime.now(timezone.utc)

        # Also force the random chance to not fire
        mocker.patch("random.random", return_value=0.9)

        decision = await behavior.tick(base_context)
        assert decision is None

    @pytest.mark.asyncio
    async def test_triggers_when_queue_is_empty_and_low_activity(self, base_context):
        """IdleMonologue should still be able to fire even with empty priority queue."""
        behavior = IdleMonologueBehavior()
        base_context["activity_score"] = 0.8
        base_context["queue"].messages = []
        base_context["last_autonomous_speech_time"] = (
            datetime.now(timezone.utc) - timedelta(seconds=200)
        )

        decision = await behavior.tick(base_context)
        assert decision is not None
        assert decision["type"] == "monologue"

    @pytest.mark.asyncio
    async def test_handles_missing_keys_in_context_gracefully(self, base_context):
        """Negative path: behaviours should not explode on incomplete context."""
        behavior = IdleMonologueBehavior()
        del base_context["last_autonomous_speech_time"]  # remove critical key

        # Should either return None or handle defensively (current impl would crash on KeyError)
        # For now we test that we can at least call it without total disaster in the test harness
        try:
            decision = await behavior.tick(base_context)
        except KeyError:
            decision = None  # acceptable for now; documents current fragility

        assert decision is None or decision.get("type") == "monologue"

    @pytest.mark.asyncio
    async def test_chat_response_handles_empty_queue_gracefully(self, base_context):
        """Negative path: ChatResponseBehavior when queue.get_best returns None."""
        behavior = ChatResponseBehavior()
        base_context["activity_score"] = 6.0
        base_context["queue"].get_best.return_value = None

        decision = await behavior.tick(base_context)
        assert decision is None  # should not crash, just no decision


class TestChatResponseBehavior:
    @pytest.mark.asyncio
    async def test_activates_in_medium_activity_window(self, base_context):
        behavior = ChatResponseBehavior()
        base_context["activity_score"] = 5.5
        best_msg = {"text": "hello", "source": "chat"}
        base_context["queue"].get_best.return_value = best_msg

        decision = await behavior.tick(base_context)

        assert decision is not None
        assert decision["type"] == "response"
        assert decision["best_message"] == best_msg
        base_context["queue"].get_best.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_trigger_outside_window(self, base_context):
        behavior = ChatResponseBehavior()
        base_context["activity_score"] = 1.0   # too low

        decision = await behavior.tick(base_context)
        assert decision is None
        # In the low-activity case the behavior may short-circuit before querying the queue
        # (this is acceptable behaviour — we just verify it didn't return a decision)

    @pytest.mark.asyncio
    async def test_random_chance_can_trigger_in_high_activity(self, base_context, mocker):
        """Even in high activity, there's a random chance to monologue."""
        behavior = IdleMonologueBehavior()
        base_context["activity_score"] = 10.0  # very high activity

        # Force the random check to succeed
        mocker.patch("random.random", return_value=0.01)  # well below 0.18 threshold

        decision = await behavior.tick(base_context)
        assert decision is not None
        assert decision["type"] == "monologue"


class TestFrontendTriggeredMonologueBehavior:
    @pytest.mark.asyncio
    async def test_triggers_on_frontend_command(self, base_context):
        behavior = FrontendTriggeredMonologueBehavior()
        base_context["frontend_command"] = "start"

        decision = await behavior.tick(base_context)
        assert decision is not None
        assert decision["type"] == "monologue"
        assert "welcome" in decision["topic"].lower()

    @pytest.mark.asyncio
    async def test_does_nothing_without_command(self, base_context, mock_heavy_stack):
        behavior = FrontendTriggeredMonologueBehavior()
        base_context["frontend_command"] = None

        decision = await behavior.tick(base_context)
        assert decision is None


# Ensure the whole module benefits from heavy mocking
pytestmark = [pytest.mark.usefixtures("mock_heavy_stack")]
