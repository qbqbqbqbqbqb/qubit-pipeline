import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.qubit.cognitive.behaviours.idle_monologue import IdleMonologueBehavior
from src.qubit.cognitive.behaviours.chat_response import ChatResponseBehavior
from src.qubit.cognitive.behaviours.frontend_monologue import FrontendTriggeredMonologueBehavior


@pytest.fixture
def base_context():
    now = datetime.now(timezone.utc)
    queue = MagicMock()
    queue.get_best.return_value = None
    return {
        "activity_score": 0.0,
        "queue": queue,
        "features": {"monologue": True, "stt": True},
        "last_autonomous_speech_time": now - timedelta(seconds=100),
        "last_user_input_response_time": now - timedelta(seconds=100),
        "frontend_command": None,
    }


class TestIdleMonologueBehavior:
    @pytest.mark.asyncio
    async def test_triggers_on_low_activity(self, base_context):
        behavior = IdleMonologueBehavior()
        base_context["activity_score"] = 1.5

        decision = await behavior.tick(base_context)
        assert decision is not None
        assert decision["type"] == "monologue"

    @pytest.mark.asyncio
    async def test_respects_monologue_disabled(self, base_context):
        behavior = IdleMonologueBehavior()
        base_context["features"]["monologue"] = False
        base_context["activity_score"] = 0.5

        decision = await behavior.tick(base_context)
        assert decision is None


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

    @pytest.mark.asyncio
    async def test_does_not_trigger_outside_window(self, base_context):
        behavior = ChatResponseBehavior()
        base_context["activity_score"] = 1.0   # too low

        decision = await behavior.tick(base_context)
        assert decision is None


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
    async def test_does_nothing_without_command(self, base_context):
        behavior = FrontendTriggeredMonologueBehavior()
        base_context["frontend_command"] = None

        decision = await behavior.tick(base_context)
        assert decision is None
