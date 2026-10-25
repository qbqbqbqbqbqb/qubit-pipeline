"""Tests for new RuntimeState fields added this session."""

import pytest
from src.qubit.core.runtime_state import RuntimeState, FeatureFlags


def test_feature_flags_has_chat_logging():
    flags = FeatureFlags()
    assert flags.chat_logging is False


def test_feature_flags_has_processing_active():
    flags = FeatureFlags()
    assert flags.processing_active is True


def test_feature_flags_has_vision():
    flags = FeatureFlags()
    assert flags.vision is False


def test_runtime_state_has_stream_type():
    state = RuntimeState()
    assert isinstance(state.stream_type, str)
    assert state.stream_type  # non-empty (from settings default)


def test_runtime_state_has_vision_window():
    state = RuntimeState()
    assert hasattr(state, "vision_window")
    assert isinstance(state.vision_window, str)


def test_runtime_state_has_latest_vision_description():
    state = RuntimeState()
    assert state.latest_vision_description == ""


def test_runtime_state_has_current_obs_scene():
    state = RuntimeState()
    assert state.current_obs_scene == ""


def test_runtime_state_has_health_dict():
    state = RuntimeState()
    assert isinstance(state.health, dict)
    assert len(state.health) == 0


def test_processing_active_can_be_set_false():
    state = RuntimeState()
    state.features.processing_active = False
    assert state.features.processing_active is False


def test_stream_type_can_be_changed():
    state = RuntimeState()
    state.stream_type = "Minecraft"
    assert state.stream_type == "Minecraft"


def test_health_dict_can_be_updated():
    state = RuntimeState()
    state.health["twitch_listener"] = {"status": "connected", "detail": ""}
    assert state.health["twitch_listener"]["status"] == "connected"


def test_vision_description_can_be_updated():
    state = RuntimeState()
    state.latest_vision_description = "Player is in inventory screen."
    assert "inventory" in state.latest_vision_description