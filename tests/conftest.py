"""
Root conftest.py for the entire test suite.

See tests/AGENTS.md for the full testing & mocking strategy.

Key fixtures:
- mock_heavy_stack: The main tool for isolating tests from torch, transformers, chromadb, twitchAPI, audio libs, etc.
- mock_app, event_bus, sample_event: Common core fixtures.

Subdirectories (models/, memory/, core/, cognitive/, etc.) have their own conftest.py files
that apply directory-level markers and fixtures.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.event_bus import EventBus
from src.qubit.core.events import Event


# =============================================================================
# Custom Markers
# =============================================================================
def pytest_configure(config):
    """Register custom markers so we don't get PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers", "heavy: tests that require heavy mocking of ML/external services"
    )


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def sample_event():
    return Event(
        type="test_event",
        timestamp="2025-05-24T12:00:00Z",
        data={"key": "value", "source": "test"}
    )


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.event_bus = EventBus()
    app.state = MagicMock()
    app.state.start = asyncio.Event()
    app.state.shutdown = asyncio.Event()
    app.logger = MagicMock()
    return app


@pytest.fixture
def mock_heavy_stack(mocker):
    """
    Opt-in fixture that heavily mocks the ML / external service stack.

    Recommended usage in any test involving:
        - LLM / model loading
        - ChromaDB / long-term memory
        - Twitch / external realtime APIs
        - Audio synthesis or device I/O
        - OBS / VTube / side-effecty output handlers

    Add `mock_heavy_stack` to your test signature (or use it via
    `pytest.mark.usefixtures`) to keep tests fast, deterministic,
    and runnable in minimal environments.

    Example:
        def test_something(mock_heavy_stack):
            ...
    """
    targets = [
        # Our internal heavy classes (safe to patch)
        "src.qubit.models.model_manager.ModelManager",
        "src.qubit.models.async_hf_model_manager.AsyncHuggingFaceLLM",
        "src.qubit.models.hf_model_manager.HuggingFaceModelManager",
        "src.qubit.memory.memory_service.chromadb",
        "src.qubit.input.twitch.listener.TwitchListener",
        "src.qubit.output.tts_handler.TTSHandler",
        "src.qubit.output.obs_handler.OBSHandler",
    ]
    for target in targets:
        try:
            mocker.patch(target, create=True)
        except Exception:
            # Some dotted paths may not be importable yet; safe to skip in broad mocking
            pass

    # For top-level heavy packages, pre-populate in sys.modules if not present
    # (this is safer than patch on bare module names)
    import sys
    for mod_name in ["torch", "transformers", "chromadb", "twitchAPI", "numpy", "pyaudio", "piper"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock(name=mod_name)

    return None