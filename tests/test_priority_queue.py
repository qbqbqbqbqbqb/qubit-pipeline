"""Tests for InputPriorityQueue."""

import time
import pytest
from unittest.mock import MagicMock
from src.qubit.cognitive.priority_queue import InputPriorityQueue


def _msg(text="hello", source="user_input_chat_message"):
    event = MagicMock()
    event.type = source
    return text, source, event


def test_add_chat_message_increases_size():
    q = InputPriorityQueue()
    text, source, event = _msg()
    q.add(text, source, event)
    assert len(q.chat_messages) == 1


def test_add_stt_message_goes_to_stt_bucket():
    q = InputPriorityQueue()
    text, _, event = _msg()
    q.add(text, "user_input_stt", event)
    assert len(q.stt_messages) == 1
    assert len(q.chat_messages) == 0


def test_get_best_prefers_stt_over_chat():
    q = InputPriorityQueue()
    chat_event = MagicMock()
    stt_event = MagicMock()
    q.add("chat msg", "user_input_chat_message", chat_event)
    q.add("stt msg", "user_input_stt", stt_event)
    best = q.get_best()
    assert best["source"] == "user_input_stt"


def test_get_best_returns_none_when_empty():
    q = InputPriorityQueue()
    assert q.get_best() is None


def test_remove_by_id_removes_correct_message():
    q = InputPriorityQueue()
    e1 = MagicMock()
    e2 = MagicMock()
    q.add("first", "user_input_chat_message", e1)
    q.add("second", "user_input_chat_message", e2)

    first = q.chat_messages[0]
    q.remove(first)

    assert len(q.chat_messages) == 1
    assert q.chat_messages[0]["text"] == "second"


def test_remove_nonexistent_message_is_noop():
    q = InputPriorityQueue()
    fake = {"_id": "does-not-exist", "text": "x"}
    q.remove(fake)  # should not raise


def test_remove_message_without_id_is_noop():
    q = InputPriorityQueue()
    q.remove({"text": "no id here"})


def test_message_gets_unique_ids():
    q = InputPriorityQueue()
    e = MagicMock()
    q.add("a", "user_input_chat_message", e)
    q.add("b", "user_input_chat_message", e)
    ids = {m["_id"] for m in q.chat_messages}
    assert len(ids) == 2


def test_chat_maxlen_enforced():
    q = InputPriorityQueue(maxlen=3)
    e = MagicMock()
    for i in range(5):
        q.add(f"msg {i}", "user_input_chat_message", e)
    assert len(q.chat_messages) <= 3


def test_stt_slots_enforced():
    q = InputPriorityQueue(stt_slots=2)
    e = MagicMock()
    for i in range(4):
        q.add(f"stt {i}", "user_input_stt", e)
    assert len(q.stt_messages) <= 2


def test_has_source_true():
    q = InputPriorityQueue()
    q.add("hello", "user_input_chat_message", MagicMock())
    assert q.has_source("user_input_chat_message") is True


def test_has_source_false_when_empty():
    q = InputPriorityQueue()
    assert q.has_source("user_input_chat_message") is False


def test_quality_question_bonus():
    q = InputPriorityQueue()
    quality_with = q._calculate_quality("is this a question?")
    quality_without = q._calculate_quality("this is not a question")
    assert quality_with > quality_without


def test_offmention_penalty_applied():
    whitelist = frozenset({"qubit"})
    q = InputPriorityQueue(mention_whitelist=whitelist)
    penalised = q._calculate_quality("@someoneelse hey")
    normal = q._calculate_quality("hey qubit")
    assert penalised < normal


def test_whitelisted_mention_gets_bonus():
    whitelist = frozenset({"qubit"})
    q = InputPriorityQueue(mention_whitelist=whitelist)
    with_mention = q._calculate_quality("@qubit what do you think?")
    without_mention = q._calculate_quality("what do you think?")
    assert with_mention > without_mention


def test_mixed_mention_whitelisted_wins():
    whitelist = frozenset({"qubit"})
    q = InputPriorityQueue(mention_whitelist=whitelist)
    score = q._calculate_quality("@qubit and @someoneelse hello")
    # Should get bonus, not penalty
    assert score > q._calculate_quality("hello there")


def test_empty_whitelist_no_penalty():
    q = InputPriorityQueue(mention_whitelist=frozenset())
    score = q._calculate_quality("@someoneelse hey")
    assert score >= 0.0


def test_stale_messages_excluded_from_get_best():
    q = InputPriorityQueue(max_age_seconds=0.01)
    q.add("old msg", "user_input_chat_message", MagicMock())
    time.sleep(0.05)
    assert q.get_best() is None
