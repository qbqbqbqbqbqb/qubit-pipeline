import asyncio
from twitch_bot import Bot
from refresh_token import refresh_twitch_token 

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Main")

async def token_refresher_loop():
    while True:
        try:
            logger.info("[Token Refresh] Refreshing Twitch token...")
            await refresh_twitch_token()
            logger.info("[Token Refresh] Refresh complete")
        except Exception as e:
            logger.error(f"[Token Refresh] Failed to refresh token: {e}")

        await asyncio.sleep(3600)  

async def main():
    """
    Entry point for running the bot asynchronously.

    - Logs the start of the bot.
    - Logs and starts the token refresher loop.
    - Initialises and starts the Bot instance.
    - Logs a warning if the bot's start method returns unexpectedly.
    - Catches and logs any critical exceptions that occur during execution.
    """
    bot = Bot()

    try:
        logger.info("[Main] Refreshing token before bot start...")
        await refresh_twitch_token()
        
        logger.info("[Main] Starting Bot and Token Refresher...")
        
        bot_task = asyncio.create_task(bot.start()) 
        refresher_task = asyncio.create_task(token_refresher_loop())

        await bot_task
        
    except KeyboardInterrupt:
        logger.info("[Main] KeyboardInterrupt received. Shutting down...")
        bot.shutdown_event.set()

        refresher_task.cancel()
        await asyncio.gather(refresher_task, return_exceptions=True)

        await bot_task
        logger.info("[Main] Bot has exited. Token refresher cancelled.")
    
    except Exception as e:
        logger.critical(f"[main] ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
