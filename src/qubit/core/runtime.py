"""Application startup, signal handling, and shutdown coordination."""

import asyncio
import signal
from datetime import datetime, timezone

from src.qubit.core.events import Event
from src.qubit.utils.log_utils import get_logger

logger = get_logger(__name__)


async def run_app(app):
    """Start all services, wait for the frontend start command, then run until shutdown."""
    tasks = []

    for service in app.services:
        task = asyncio.create_task(service.start(app))
        tasks.append(task)

    logger.info("Bot initialised. Waiting for startup command from browser.")
    await app.state.start.wait()
    logger.info("Bot started.")

    await app.event_bus.publish(Event(
        type="bot_started",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={"status": "active"},
    ))

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, app.state.shutdown.set)
    loop.add_signal_handler(signal.SIGTERM, app.state.shutdown.set)

    await app.state.shutdown.wait()
    logger.info("Shutdown signal received — stopping services.")

    for service in reversed(app.services):
        await service.stop()

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete.")
