import asyncio
from twitch_bot import Bot

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Main")

async def main():
    """
    Entry point for running the bot asynchronously.

    - Logs the start of the bot.
    - Initialises and starts the Bot instance.
    - Logs a warning if the bot's start method returns unexpectedly.
    - Catches and logs any critical exceptions that occur during execution.
    """
    try:
        logger.info("[Main] Starting Bot...")
        bot = Bot()
        await bot.start()
        logger.warning("[Main] Bot.start() has returned. Exiting main()")
    except Exception as e:
        logger.critical(f"[main] ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())