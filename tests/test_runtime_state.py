"""Tests for RuntimeState and FeatureFlags."""

import asyncio
import pytest
from src.qubit.core.runtime_state import RuntimeState, FeatureFlags


def test_feature_flags_defaults():
    flags = FeatureFlags()
    assert flags.twitch is True
    assert flags.kick is True
    assert flags.stt is True
    assert flags.chat is True
    assert flags.raids is True
    assert flags.follow is True
    assert flags.subs is True
    assert flags.gifts is True
    assert flags.monologue is True
    assert flags.vtube_studio is True
    assert flags.png_output is False


def test_feature_flags_attribute_access():
    flags = FeatureFlags()
    flags.monologue = False
    assert flags.monologue is False


def test_feature_flags_typo_raises():
    flags = FeatureFlags()
    with pytest.raises(AttributeError):
        _ = flags.nonexistent_flag


def test_runtime_state_initialises_events():
    state = RuntimeState()
    assert isinstance(state.shutdown, asyncio.Event)
    assert isinstance(state.start, asyncio.Event)
    assert isinstance(state.ai_speaking, asyncio.Event)
    assert isinstance(state.ai_thinking, asyncio.Event)


def test_runtime_state_events_initially_unset():
    state = RuntimeState()
    assert not state.shutdown.is_set()
    assert not state.start.is_set()
    assert not state.ai_speaking.is_set()
    assert not state.ai_thinking.is_set()


def test_runtime_state_has_feature_flags():
    state = RuntimeState()
    assert isinstance(state.features, FeatureFlags)


@pytest.mark.asyncio
async def test_shutdown_event_can_be_set_and_awaited():
    state = RuntimeState()
    state.shutdown.set()
    assert state.shutdown.is_set()
    await asyncio.wait_for(state.shutdown.wait(), timeout=0.1)


@pytest.mark.asyncio
async def test_ai_speaking_toggle():
    state = RuntimeState()
    assert not state.ai_speaking.is_set()
    state.ai_speaking.set()
    assert state.ai_speaking.is_set()
    state.ai_speaking.clear()
    assert not state.ai_speaking.is_set()
