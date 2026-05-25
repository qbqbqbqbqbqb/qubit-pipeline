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
        q = InputPriorityQueue()
        old_msg = {
            "text": "old",
            "source": "user_input_stt",
            "timestamp": datetime.now(timezone.utc) - timedelta(minutes=10),
            "base_priority": 10.0,
            "quality": 1.0,
            "event": {}
        }
        q.messages.append(old_msg)
        q.add("fresh stt input", "user_input_stt", {})

        best = q.get_best()
        assert best["text"] == "fresh stt input"

    def test_remove_message(self):
        q = InputPriorityQueue()
        q.add("to be removed", "user_input_chat_message", {})
        msg = q.get_best()
        q.remove(msg)
        assert q.get_best() is None

    def test_maxlen_eviction(self):
        q = InputPriorityQueue(maxlen=2)
        q.add("one", "user_input_chat_message", {})
        q.add("two", "user_input_chat_message", {})
        q.add("three", "user_input_chat_message", {})
        assert len(q.messages) == 2
