import asyncio
import signal

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
