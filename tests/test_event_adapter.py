"""Tests for EventAdapter — source mapping, feature flag resolution, text/detail extraction."""

import pytest
from unittest.mock import MagicMock
from src.qubit.cognitive.activity.event_adapter import EventAdapter


def _event(type_, **attrs):
    e = MagicMock()
    e.type = type_
    e.data = {}
    for k, v in attrs.items():
        setattr(e, k, v)
    return e


# --- get_source ---

def test_get_source_twitch_chat():
    # EventAdapter receives *_filtered events — chat/stt arrive post-ConversationProcessor.
    e = _event("twitch_chat_filtered")
    assert EventAdapter.get_source(e) == "user_input_chat_message"


def test_get_source_kick_chat():
    e = _event("kick_chat_filtered")
    assert EventAdapter.get_source(e) == "user_input_chat_message"


def test_get_source_stt():
    e = _event("stt_filtered")
    assert EventAdapter.get_source(e) == "user_input_stt"


def test_get_source_twitch_chat_processed_is_unknown():
    # *_processed chat events no longer reach EventAdapter — confirm they resolve to DEFAULT_SOURCE.
    e = _event("twitch_chat_processed")
    assert EventAdapter.get_source(e) == EventAdapter.DEFAULT_SOURCE


def test_get_source_twitch_raid():
    e = _event("twitch_raid_processed")
    assert EventAdapter.get_source(e) == "user_event_raid"


def test_get_source_twitch_subscription():
    e = _event("twitch_subscription_processed")
    assert EventAdapter.get_source(e) == "user_event_subscription"


def test_get_source_twitch_follow():
    e = _event("twitch_follow_processed")
    assert EventAdapter.get_source(e) == "user_event_follow"


def test_get_source_kick_raid():
    e = _event("kick_raid_processed")
    assert EventAdapter.get_source(e) == "user_event_raid"


def test_get_source_unknown_defaults():
    e = _event("totally_unknown_event")
    assert EventAdapter.get_source(e) == EventAdapter.DEFAULT_SOURCE


# --- feature_flag_for ---

def test_feature_flag_chat():
    assert EventAdapter.feature_flag_for("user_input_chat_message", MagicMock()) == "chat"


def test_feature_flag_stt():
    assert EventAdapter.feature_flag_for("user_input_stt", MagicMock()) == "stt"


def test_feature_flag_raid():
    assert EventAdapter.feature_flag_for("user_event_raid", MagicMock()) == "raids"


def test_feature_flag_follow():
    assert EventAdapter.feature_flag_for("user_event_follow", MagicMock()) == "raids"


def test_feature_flag_non_gift_sub_returns_raids():
    e = _event("twitch_subscription_processed", sub_type="prime")
    assert EventAdapter.feature_flag_for("user_event_subscription", e) == "raids"


def test_feature_flag_gift_sub_returns_gifts():
    e = _event("twitch_subscription_processed", sub_type="gift")
    assert EventAdapter.feature_flag_for("user_event_subscription", e) == "gifts"


def test_feature_flag_gift_sub_case_insensitive():
    e = _event("twitch_subscription_processed", sub_type="GIFT")
    assert EventAdapter.feature_flag_for("user_event_subscription", e) == "gifts"


# --- extract_text ---

def test_extract_text_from_attribute():
    e = _event("twitch_chat_processed", text="hello world")
    assert EventAdapter.extract_text(e) == "hello world"


def test_extract_text_from_data_dict():
    e = MagicMock()
    e.type = "twitch_chat_processed"
    del e.text  # ensure attribute access raises
    e.data = {"text": "from data"}
    # Mock attribute access to raise AttributeError
    type(e).text = property(lambda self: (_ for _ in ()).throw(AttributeError()))
    assert EventAdapter.extract_text(e) == "from data"


def test_extract_text_empty_fallback():
    e = MagicMock()
    e.type = "twitch_chat_processed"
    e.text = None
    e.data = {}  # real dict so .get("text", "") returns ""
    assert EventAdapter.extract_text(e) == ""


# --- extract_event_detail ---

def test_extract_raid_detail():
    e = _event("twitch_raid_processed", user="raider1", viewers=123)
    detail = EventAdapter.extract_event_detail(e, "user_event_raid")
    assert detail["kind"] == "raid"
    assert detail["username"] == "raider1"
    assert detail["viewer_count"] == 123


def test_extract_follow_detail():
    e = _event("twitch_follow_processed", user="follower1")
    detail = EventAdapter.extract_event_detail(e, "user_event_follow")
    assert detail["kind"] == "follow"
    assert detail["username"] == "follower1"


def test_extract_subscription_detail():
    e = _event("twitch_subscription_processed", user="subber1", tier="1000", sub_type="prime")
    detail = EventAdapter.extract_event_detail(e, "user_event_subscription")
    assert detail["kind"] == "subscription"
    assert detail["username"] == "subber1"
    assert detail["tier"] == "1000"
    assert detail["sub_type"] == "prime"


def test_extract_detail_missing_user_defaults():
    e = _event("twitch_follow_processed")
    e.user = None
    detail = EventAdapter.extract_event_detail(e, "user_event_follow")
    assert detail["username"] == "someone"


# --- EVENT_SOURCES membership ---

def test_community_sources_in_event_sources():
    for source in ("user_event_raid", "user_event_subscription", "user_event_follow"):
        assert source in EventAdapter.EVENT_SOURCES


def test_chat_source_not_in_event_sources():
    assert "user_input_chat_message" not in EventAdapter.EVENT_SOURCES
