import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.event_bus import EventBus
from src.qubit.core.events import Event


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