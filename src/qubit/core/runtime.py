"""Application startup, signal handling, and shutdown coordination."""

import asyncio
import signal
from datetime import datetime, timezone

from src.qubit.core.events import Event
from src.qubit.utils.log_utils import get_logger

logger = get_logger(__name__)


async def run_app(app) -> None:
    """
    Drive the full application lifecycle.

    Startup order:
    1. Attach all services (bind app, register subscriptions).
    2. Launch services that do not wait for the start signal immediately
       (e.g. WebSocketServer needs to be running to receive the signal).
    3. Wait for the frontend start command.
    4. Launch all remaining services.
    5. Publish bot_started so processors and behaviours know we're live.
    6. Wait for shutdown signal, then tear everything down in reverse order.
    """
    # Phase 1 — attach every service so subscriptions are live.
    for service in app.services:
        service.attach(app)

    # Phase 2 — launch pre-start services immediately.
    pre_start = [s for s in app.services if not s.WAIT_FOR_START]
    for service in pre_start:
        service.launch()
        logger.info("[run_app] Pre-start service launched: %s", service.name)

    # Phase 3 — wait for frontend.
    logger.info("[run_app] Waiting for start command from frontend.")
    await app.state.start.wait()
    logger.info("[run_app] Start command received.")

    # Phase 4 — launch remaining services.
    post_start = [s for s in app.services if s.WAIT_FOR_START]
    for service in post_start:
        service.launch()

    # Phase 5 — notify the bus.
    await app.event_bus.publish(Event(
        type="bot_started",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={"status": "active"},
    ))

    # Phase 6 — wait for shutdown.
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, app.state.shutdown.set)
    loop.add_signal_handler(signal.SIGTERM, app.state.shutdown.set)

    await app.state.shutdown.wait()
    logger.info("[run_app] Shutdown signal received — stopping services.")

    for service in reversed(app.services):
        await service.stop()

    logger.info("[run_app] Shutdown complete.")
