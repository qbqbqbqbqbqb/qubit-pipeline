import sys
import os
from scripts.llm.model_manager import ModelManager
import asyncio
from scripts.bot.twitch_bot import Bot as TwitchBot
from scripts.core.controller import Controller

from scripts.utils.refresh_token import refresh_twitch_token

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
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
    Entry point for running the bot.

    - Preloads the LLM model
    - Runs the bot when user presses start
    """

    model_manager = ModelManager()
    logger.info("[Main] LLM model preloaded")

    controller = Controller()
    await controller.run()


if __name__ == "__main__":
    asyncio.run(main())
