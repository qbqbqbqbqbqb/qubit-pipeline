"""Tests for ChatLogger — training data JSONL writer."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.qubit.processing.chat_logger import ChatLogger
from src.qubit.core.runtime_state import RuntimeState


def _event(type_="twitch_chat_filtered", text="hello", user="viewer1"):
    e = MagicMock()
    e.type = type_
    e.data = {"text": text, "user": user}
    return e


def _make_state(logging_on=True):
    state = RuntimeState()
    state.features.chat_logging = logging_on
    return state


@pytest.fixture
def tmp_log(tmp_path):
    return tmp_path / "chat_training.jsonl"


@pytest.fixture
def logger_on(tmp_log):
    app = MagicMock()
    app.state = _make_state(logging_on=True)
    logger = ChatLogger(runtime_state=app.state, log_path=tmp_log)
    return logger


@pytest.fixture
def logger_off(tmp_log):
    app = MagicMock()
    app.state = _make_state(logging_on=False)
    logger = ChatLogger(runtime_state=app.state, log_path=tmp_log)
    return logger


@pytest.mark.asyncio
async def test_twitch_message_written_when_on(logger_on, tmp_log):
    await logger_on.handle_event(_event("twitch_chat_filtered", "nice stream", "alice"))
    lines = tmp_log.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["source"] == "twitch"
    assert entry["user"] == "alice"
    assert entry["text"] == "nice stream"


@pytest.mark.asyncio
async def test_kick_message_written_when_on(logger_on, tmp_log):
    await logger_on.handle_event(_event("kick_chat_filtered", "hello", "bob"))
    entry = json.loads(tmp_log.read_text().splitlines()[0])
    assert entry["source"] == "kick"


@pytest.mark.asyncio
async def test_stt_message_written_with_streamer_user(logger_on, tmp_log):
    e = MagicMock()
    e.type = "stt_filtered"
    e.data = {"text": "I said something", "user": None}
    await logger_on.handle_event(e)
    entry = json.loads(tmp_log.read_text().splitlines()[0])
    assert entry["source"] == "stt"
    assert entry["user"] == "streamer"


@pytest.mark.asyncio
async def test_nothing_written_when_flag_off(logger_off, tmp_log):
    await logger_off.handle_event(_event())
    assert not tmp_log.exists()


@pytest.mark.asyncio
async def test_empty_text_not_written(logger_on, tmp_log):
    await logger_on.handle_event(_event(text=""))
    assert not tmp_log.exists()


@pytest.mark.asyncio
async def test_multiple_messages_appended(logger_on, tmp_log):
    await logger_on.handle_event(_event(text="first"))
    await logger_on.handle_event(_event(text="second"))
    lines = tmp_log.read_text().splitlines()
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_entry_has_timestamp(logger_on, tmp_log):
    await logger_on.handle_event(_event())
    entry = json.loads(tmp_log.read_text().splitlines()[0])
    assert "timestamp" in entry
    # Should be a valid ISO timestamp
    datetime.fromisoformat(entry["timestamp"])


@pytest.mark.asyncio
async def test_log_directory_created_if_missing(tmp_path):
    nested = tmp_path / "deep" / "nested" / "log.jsonl"
    state = _make_state(logging_on=True)
    logger = ChatLogger(runtime_state=state, log_path=nested)
    await logger.handle_event(_event(text="test"))
    assert nested.exists()


@pytest.mark.asyncio
async def test_no_runtime_state_is_noop(tmp_log):
    logger = ChatLogger(runtime_state=None, log_path=tmp_log)
    await logger.handle_event(_event())
    assert not tmp_log.exists()