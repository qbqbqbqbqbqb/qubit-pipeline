"""Tests for Service supervisor loop — restart on crash, backoff, health reporting."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.qubit.core.service import Service
from src.qubit.core.runtime_state import RuntimeState
from src.qubit.core.event_bus import EventBus


def _make_app():
    app = MagicMock()
    app.state = RuntimeState()
    app.event_bus = EventBus()
    return app


class _FailOnceService(Service):
    """Fails the first _run() call, succeeds the second."""
    def __init__(self):
        super().__init__("fail_once")
        self.run_count = 0

    async def _run(self):
        self.run_count += 1
        if self.run_count == 1:
            raise RuntimeError("first run failure")
        # Second run — return cleanly

    async def stop(self):
        pass


class _AlwaysFailService(Service):
    MAX_RESTARTS = 2

    def __init__(self):
        super().__init__("always_fail")
        self.run_count = 0

    async def _run(self):
        self.run_count += 1
        raise RuntimeError("always fails")

    async def stop(self):
        pass


class _CleanExitService(Service):
    MAX_RESTARTS = 3

    def __init__(self):
        super().__init__("clean_exit")
        self.ran = False

    async def _run(self):
        self.ran = True
        # Returns without raising — clean exit, no restart

    async def stop(self):
        pass


def test_set_connected_updates_health():
    svc = Service("test_svc")
    svc.app = _make_app()
    svc._set_connected()
    assert svc.app.state.health["test_svc"]["status"] == "connected"


def test_set_disconnected_updates_health():
    svc = Service("test_svc")
    svc.app = _make_app()
    svc._set_disconnected("timeout")
    h = svc.app.state.health["test_svc"]
    assert h["status"] == "disconnected"
    assert h["detail"] == "timeout"


def test_report_health_with_no_app_does_not_raise():
    svc = Service("test_svc")
    svc.app = None
    svc._report_health("connected")  # should not raise


@pytest.mark.asyncio
async def test_clean_exit_does_not_restart():
    svc = _CleanExitService()
    svc.app = _make_app()
    await asyncio.wait_for(svc._supervised_run(), timeout=2.0)
    assert svc.ran is True
    # _run returns cleanly on first call; supervisor should not restart


@pytest.mark.asyncio
async def test_always_fail_gives_up_after_max_restarts():
    svc = _AlwaysFailService()
    svc._BASE_BACKOFF = 0.001  # speed up test
    svc.app = _make_app()
    await asyncio.wait_for(svc._supervised_run(), timeout=5.0)
    # Should have run MAX_RESTARTS + 1 times then given up
    assert svc.run_count == svc.MAX_RESTARTS + 1


@pytest.mark.asyncio
async def test_always_fail_sets_error_health():
    svc = _AlwaysFailService()
    svc._BASE_BACKOFF = 0.001
    svc.app = _make_app()
    await asyncio.wait_for(svc._supervised_run(), timeout=5.0)
    assert svc.app.state.health.get("always_fail", {}).get("status") == "error"


@pytest.mark.asyncio
async def test_cancelled_error_exits_cleanly():
    class _HangsForever(Service):
        MAX_RESTARTS = 0
        async def _run(self):
            await asyncio.sleep(9999)
        async def stop(self):
            pass

    svc = _HangsForever("hang")
    svc.app = _make_app()
    task = asyncio.create_task(svc._supervised_run())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected


def test_attach_registers_subscriptions():
    class _SubService(Service):
        SUBSCRIPTIONS = {"test_event": "handle_event"}
        async def handle_event(self, e): pass
        async def _run(self): pass
        async def stop(self): pass

    svc = _SubService("sub_svc")
    app = _make_app()
    svc.attach(app)
    assert svc.app is app
    assert "test_event" in app.event_bus.subscribers