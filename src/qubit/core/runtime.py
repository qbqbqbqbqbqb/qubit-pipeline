"""
Runtime entry point.

Responsibilities (see ARCHITECTURE.md):
- Start all registered Services in parallel
- Wait for the frontend "start" signal via RuntimeState
- Publish the bot_started event
- Handle graceful shutdown (SIGINT/SIGTERM)
- Stop all services in reverse order

This is pure infrastructure. No domain logic lives here.
"""

import asyncio
from datetime import datetime, timezone
import signal
from src.qubit.core.events import Event
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


async def run_app(app):

    tasks = []

    for service in app.services:
        task = asyncio.create_task(service.start(app))
        tasks.append(task)

    logger.info("Bot initialised. Waiting for startup command from browser.")
    await app.state.start.wait()

    logger.info(" Bot started")

    # This event is the trigger that many components (Cognitive, Generation, Output) wait for
    event = Event(
            type="bot_started",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"status": "active"},
        )
    await app.event_bus.publish(event)

    def shutdown():
        app.state.shutdown.set()

    signal.signal(signal.SIGINT, lambda s, f: shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: shutdown())

    await app.state.shutdown.wait()

    for service in app.services:
        await service.stop()

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
