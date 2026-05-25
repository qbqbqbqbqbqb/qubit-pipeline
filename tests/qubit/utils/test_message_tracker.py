import pytest
from src.qubit.utils.message_tracker import MessageTracker


def test_message_tracker_initialization():
    tracker = MessageTracker()
    assert tracker.recent_expiry == 60
    assert tracker.response_expiry == 60
    # maxlen is not stored as an attribute; we can only infer from behavior if needed.


def test_message_tracker_add_message():
    tracker = MessageTracker()
    tracker.add_message("hello world")
    assert "hello world" in tracker.last_seen


def test_message_tracker_is_repeated_false_for_new():
    tracker = MessageTracker(recent_expiry=10)
    assert tracker.is_repeated("new message") is False


def test_message_tracker_is_repeated_true_within_expiry():
    tracker = MessageTracker(recent_expiry=10)
    tracker.add_message("repeat me")
    # Immediately after adding, should be repeated
    assert tracker.is_repeated("repeat me") is True


def test_message_tracker_is_repeated_false_after_expiry():
    tracker = MessageTracker(recent_expiry=0)  # expire immediately
    tracker.add_message("expire fast")
    assert tracker.is_repeated("expire fast") is False
