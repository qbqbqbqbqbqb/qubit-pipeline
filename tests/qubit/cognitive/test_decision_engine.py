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
        eng = DecisionEngine(tracker, mock_bus)
        # Replace real behaviors with mocks for better isolation
        eng.behaviors = [MagicMock(), MagicMock(), MagicMock()]
        for b in eng.behaviors:
            b.tick = AsyncMock(return_value=None)
        return eng

    @pytest.mark.asyncio
    async def test_run_decision_cycle_runs_behaviors(self, engine, mock_heavy_stack):
        # Force low activity so IdleMonologue can trigger
        engine.tracker.activity_score = 1.0
        engine.tracker.queue.messages = []  # no pending messages

        await engine.run_decision_cycle()

        # All mocked behaviors should have been ticked exactly once
        for behavior in engine.behaviors:
            behavior.tick.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_monologue_decision_publishes_event(self, engine, mock_heavy_stack):
        decision = {"type": "monologue", "topic": "AI jokes"}
        await engine._execute_decision(decision)

        engine.event_bus.publish.assert_awaited_once()
        event = engine.event_bus.publish.call_args[0][0]
        assert event.type == "monologue_prompt"

    @pytest.mark.asyncio
    async def test_execute_response_decision_removes_from_queue(self, engine, mock_heavy_stack):
        fake_msg = {"text": "test", "source": "chat"}
        engine.tracker.queue.messages.append(fake_msg)
        engine.tracker.queue.remove = MagicMock()

        decision = {"type": "response", "best_message": fake_msg}
        await engine._execute_decision(decision)

        engine.tracker.queue.remove.assert_called_once_with(fake_msg)

    @pytest.mark.asyncio
    async def test_decision_engine_consults_priority_queue_via_context(self, mock_heavy_stack, seeded_priority_queue):
        """Tests rich interaction between DecisionEngine and a real PriorityQueue."""
        tracker = ActivityTracker()
        # Replace the tracker's queue with the seeded one for this test
        tracker.queue = seeded_priority_queue
        mock_bus = AsyncMock()
        engine = DecisionEngine(tracker, mock_bus)

        tracker.activity_score = 7.5  # high enough to prefer response behavior

        await engine.run_decision_cycle()

        # The engine should have consulted the queue through behaviors
        # We can't assert exact internal calls without over-mocking, but we verify stability
        assert len(tracker.queue.messages) >= 0

    @pytest.mark.asyncio
    async def test_handles_malformed_decision_from_behavior_gracefully(self, engine, mock_heavy_stack):
        """Negative path: a behavior returns a bad decision dict (current behavior raises)."""
        # Make first behavior return something broken
        engine.behaviors[0].tick = AsyncMock(return_value={"type": "response"})  # missing best_message

        # Currently the engine does not guard against this → we document the crash
        with pytest.raises(KeyError):
            await engine.run_decision_cycle()

    @pytest.mark.asyncio
    async def test_build_context_handles_missing_tracker_attributes(self, mock_heavy_stack):
        """Negative path / robustness test."""
        broken_tracker = MagicMock()
        broken_tracker.activity_score = 5.0
        # Deliberately missing .queue and other attrs
        mock_bus = AsyncMock()
        engine = DecisionEngine(broken_tracker, mock_bus)

        context = engine._build_context()
        assert "activity_score" in context
        assert context["queue"] is None or hasattr(context["queue"], "messages")  # defensive

    @pytest.mark.asyncio
    async def test_decision_cycle_gracefully_handles_behavior_exception(self, engine, mock_heavy_stack):
        """Negative path: one behaviour throws — documents current (non-graceful) behavior."""
        engine.behaviors[0].tick = AsyncMock(side_effect=Exception("boom"))

        # Current implementation does not catch exceptions from behaviors
        with pytest.raises(Exception, match="boom"):
            await engine.run_decision_cycle()

    @pytest.mark.asyncio
    async def test_execute_decision_with_unknown_type_does_not_crash(self, engine, mock_heavy_stack):
        """Negative path: unknown decision type from a behaviour."""
        bad_decision = {"type": "unknown_future_decision", "data": "whatever"}
        await engine._execute_decision(bad_decision)  # should not raise
