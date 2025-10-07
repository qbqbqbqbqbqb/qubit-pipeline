import asyncio
import sys
import signal

from scripts.utils.refresh_token import refresh_twitch_token
from scripts.twitch_client import TwitchClient

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("Main")

twitch_client = None 

async def token_refresher_loop():
    while True:
        try:
            logger.info("[Token Refresh] Refreshing Twitch tokens for both accounts...")
            await refresh_twitch_token()
            logger.info("[Token Refresh] Token refresh complete")
        except Exception as e:
            logger.error(f"[Token Refresh] Failed to refresh tokens: {e}")

        await asyncio.sleep(3600)

def handle_exit(sig, frame):
    """Graceful shutdown on CTRL+C or SIGTERM."""
    logger.info(f"[Main] Caught termination signal ({sig}), shutting down...")
    if twitch_client:
        asyncio.create_task(twitch_client.disconnect())
    sys.exit(0)

async def main():
    global twitch_client

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        twitch_client = TwitchClient()

        success = await twitch_client.start()
        if not success:
            logger.error("[Main] TwitchClient failed to connect. Exiting.")
            sys.exit(1)

        logger.info("[Main] TwitchClient started successfully.")

        await refresh_twitch_token()

        await asyncio.gather(
            token_refresher_loop(), 
            keep_alive_loop(), 
        )

    except asyncio.CancelledError:
        logger.info("[Main] CancelledError caught, shutting down...")
    except KeyboardInterrupt:
        logger.info("[Main] KeyboardInterrupt received, shutting down...")
    except Exception as e:
        logger.error(f"[Main] Unexpected error: {e}")
        raise
    finally:
        if twitch_client:
            await twitch_client.disconnect()
        logger.info("[Main] Shutdown complete.")

async def keep_alive_loop():
    """Simple loop to keep main task alive until interrupted."""
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
