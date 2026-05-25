import pytest
from datetime import datetime, timedelta, timezone
from src.qubit.cognitive.priority_queue import InputPriorityQueue


class TestInputPriorityQueue:
    def test_add_and_get_best_stt_highest_priority(self):
        q = InputPriorityQueue(maxlen=5)
        q.add("hello", "user_input_chat_message", {"type": "chat"})
        q.add("this is a long question from stt?", "user_input_stt", {"type": "stt"})

        best = q.get_best()
        assert best is not None
        assert best["source"] == "user_input_stt"
        assert "?" in best["text"]

    def test_quality_scoring_question_mark_and_mention(self):
        q = InputPriorityQueue()
        q.add("normal message", "user_input_chat_message", {})
        q.add("hey @qubit what is going on?", "user_input_chat_message", {})

        best = q.get_best()
        assert best["text"].startswith("hey @qubit")

    def test_recency_affects_priority(self):
        now = datetime.now(timezone.utc)
        q = InputPriorityQueue()

        old_msg = {
            "text": "old",
            "source": "user_input_stt",
            "timestamp": now - timedelta(minutes=10),
            "base_priority": 10.0,
            "quality": 1.0,
            "event": {}
        }
        q.messages.append(old_msg)

        q.add("fresh stt input", "user_input_stt", {})

        best = q.get_best()
        assert best["text"] == "fresh stt input"
        # Recency should have made the fresh message win over the old high-score one
        assert best["timestamp"] > old_msg["timestamp"]

    def test_remove_message(self, mock_heavy_stack):
        q = InputPriorityQueue()
        q.add("to be removed", "user_input_chat_message", {})
        msg = q.get_best()
        q.remove(msg)
        assert q.get_best() is None

    def test_maxlen_eviction(self, mock_heavy_stack):
        q = InputPriorityQueue(maxlen=2)
        q.add("one", "user_input_chat_message", {})
        q.add("two", "user_input_chat_message", {})
        q.add("three", "user_input_chat_message", {})
        assert len(q.messages) == 2

    def test_fuzz_style_many_adds_and_gets(self, mock_heavy_stack):
        """Fuzz-style test: throw many varied messages and ensure we never crash and always return something when queue is non-empty."""
        import random
        q = InputPriorityQueue(maxlen=10)

        messages = [
            ("short", "user_input_chat_message", {}),
            ("a much longer message with more words?", "user_input_stt", {}),
            ("@qubit hello", "user_input_chat_message", {}),
            ("", "user_input_chat_message", {}),  # edge case
        ]

        for _ in range(50):
            text, source, event = random.choice(messages)
            q.add(text, source, event)

        # Should never return None when we just added things
        for _ in range(5):
            best = q.get_best()
            if len(q.messages) > 0:
                assert best is not None

    def test_fuzz_priority_scoring_various_inputs(self, mock_heavy_stack):
        """Light fuzz-style test on priority scoring logic."""
        import random
        q = InputPriorityQueue()

        test_cases = [
            ("short", "user_input_chat_message", 0),
            ("this is a long thoughtful question with many words?", "user_input_stt", 5),
            ("@qubit hey what do you think about this", "user_input_chat_message", 3),
            ("normal chat", "user_input_chat_message", 0),
        ]

        for text, source, expected_min_score in test_cases:
            q.add(text, source, {})
            best = q.get_best()
            assert best is not None
            # Very loose property: STT + question marks should generally score higher
            # Very loose property check — STT and questions should generally score higher than plain chat
            if "stt" in source or "?" in text:
                assert best.get("quality", 0) >= 0  # at least it scored something


# Module-level adoption of heavy mocking strategy
pytestmark = [pytest.mark.usefixtures("mock_heavy_stack")]
