import asyncio
import pytest
from src.qubit.core.runtime_state import RuntimeState


def test_runtime_state_initialization(mock_heavy_stack):
    state = RuntimeState()
    assert isinstance(state.shutdown, asyncio.Event)
    assert isinstance(state.start, asyncio.Event)
    assert state.features["twitch"] is True
    assert state.features["monologue"] is True
    assert isinstance(state.ai_speaking, asyncio.Event)
    assert isinstance(state.ai_thinking, asyncio.Event)

