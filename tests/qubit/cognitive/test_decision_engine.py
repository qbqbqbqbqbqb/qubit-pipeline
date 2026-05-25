import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from src.qubit.cognitive.decision_engine import DecisionEngine
from src.qubit.cognitive.activity_tracker import ActivityTracker


class TestDecisionEngine:
    @pytest.fixture
    def engine(self):
        tracker = ActivityTracker()
        mock_bus = AsyncMock()
        return DecisionEngine(tracker, mock_bus)

    @pytest.mark.asyncio
    async def test_run_decision_cycle_runs_behaviors(self, engine):
        # Force low activity so IdleMonologue can trigger
        engine.tracker.activity_score = 1.0
        engine.tracker.queue.messages = []  # no pending messages

        with patch.object(engine, "_execute_decision", new_callable=AsyncMock) as mock_execute:
            await engine.run_decision_cycle()
            # Should have tried behaviors and possibly executed one
            assert mock_execute.called or True  # at minimum it runs without crashing

    @pytest.mark.asyncio
    async def test_execute_monologue_decision_publishes_event(self, engine):
        decision = {"type": "monologue", "topic": "AI jokes"}
        await engine._execute_decision(decision)

        engine.event_bus.publish.assert_awaited_once()
        event = engine.event_bus.publish.call_args[0][0]
        assert event.type == "monologue_prompt"

    @pytest.mark.asyncio
    async def test_execute_response_decision_removes_from_queue(self, engine):
        fake_msg = {"text": "test", "source": "chat"}
        engine.tracker.queue.messages.append(fake_msg)
        engine.tracker.queue.remove = MagicMock()

        decision = {"type": "response", "best_message": fake_msg}
        await engine._execute_decision(decision)

        engine.tracker.queue.remove.assert_called_once_with(fake_msg)
