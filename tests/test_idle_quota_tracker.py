"""Tests for IdleQuotaTracker."""

import pytest
from src.qubit.cognitive.decision.idle_quota_tracker import IdleQuotaTracker


@pytest.fixture
def tracker():
    return IdleQuotaTracker()


def test_below_min_samples_returns_false(tracker):
    # Empty history — fewer than MIN_SAMPLES — quota returns False (not enough data yet)
    assert tracker.is_under_quota() is False


def test_catchup_bonus_when_under_quota(tracker):
    assert tracker.catchup_bonus(True) == tracker.CATCHUP_BONUS


def test_no_catchup_bonus_when_not_under_quota(tracker):
    assert tracker.catchup_bonus(False) == 0.0


def test_all_responses_meets_quota_threshold(tracker):
    # Fill with enough responses that monologue share < TARGET_SHARE
    for _ in range(tracker.MIN_SAMPLES + 5):
        tracker.record("chat_response")
    # Monologue share is 0.0 < 0.30 -> under quota
    assert tracker.is_under_quota() is True


def test_enough_monologues_satisfies_quota(tracker):
    # Fill with enough monologues to push share above TARGET_SHARE
    for _ in range(tracker.MIN_SAMPLES + 5):
        tracker.record("idle_monologue")
    # Monologue share is 1.0 >= 0.30 -> not under quota
    assert tracker.is_under_quota() is False


def test_mixed_history_at_target_not_under_quota(tracker):
    # Exactly at 30% monologue share — not under quota
    for _ in range(7):
        tracker.record("chat_response")
    for _ in range(3):
        tracker.record("idle_monologue")
    assert tracker.is_under_quota() is False


def test_history_bounded_by_history_size(tracker):
    for i in range(200):
        tracker.record("chat_response" if i % 2 == 0 else "idle_monologue")
    assert len(tracker._history) <= tracker.HISTORY_SIZE


def test_unknown_reason_not_recorded(tracker):
    tracker.record("something_else")
    assert len(tracker._history) == 0


def test_record_chat_response_adds_response_entry(tracker):
    tracker.record("chat_response")
    assert "response" in tracker._history


def test_record_idle_monologue_adds_monologue_entry(tracker):
    tracker.record("idle_monologue")
    assert "monologue" in tracker._history
