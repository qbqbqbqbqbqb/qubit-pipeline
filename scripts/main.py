import asyncio
import signal
import sys

from scripts.config import settings
from scripts.utils.log_utils import get_logger
from scripts.twitch_client import TwitchClient
from scripts.utils.refresh_token import refresh_twitch_token

logger = get_logger("Main")

stop_event = asyncio.Event()
twitch_client = None
tasks = []

def handle_signal(sig, frame):
    """Called when SIGINT or SIGTERM is received."""
    sig_name = signal.Signals(sig).name
    logger.info(f"Received signal {sig_name}, shutting down...")
    stop_event.set()

async def token_refresher_loop():
    while not stop_event.is_set():
        try:
            logger.info("Refreshing Twitch tokens...")
            await refresh_twitch_token()
            logger.info("Token refresh complete.")
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
        await asyncio.sleep(3600)

async def keep_alive_loop():
    while not stop_event.is_set():
        await asyncio.sleep(1)

async def main():
    global twitch_client, tasks

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    twitch_client = TwitchClient(settings, logger)
    success = await twitch_client.start()
    if not success:
        logger.error("Failed to start TwitchClient; exiting.")
        sys.exit(1)

    await refresh_twitch_token()

    tasks = [
        asyncio.create_task(token_refresher_loop()),
        asyncio.create_task(keep_alive_loop()),
    ]

    await stop_event.wait()

    logger.info("Canceling background tasks...")
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    await twitch_client.disconnect()
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
