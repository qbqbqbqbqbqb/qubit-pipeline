import asyncio
from scripts.utils.log_utils import get_logger
from scripts.bot.twitch_bot import Bot as TwitchBot
from scripts.utils.refresh_token import refresh_twitch_token

logger = get_logger("MainController")

async def token_refresher_loop():
    while True:
        try:
            logger.info("[Token Refresh] Refreshing Twitch tokens for both accounts...")
            await refresh_twitch_token()
            logger.info("[Token Refresh] Token refresh complete")
        except Exception as e:
            logger.error(f"[Token Refresh] Failed to refresh tokens: {e}")

        await asyncio.sleep(3600)

class Controller:
    def __init__(self,):
        pass

    async def run(self):
        try:
            print("Controller: Press Enter to start the bot...")
            input()
            logger.info("Start button pressed.")

            bot = TwitchBot()

            logger.info("[run] Refreshing tokens for both accounts...")
            await refresh_twitch_token()

            logger.info("[run] Starting Bot with dual-account token refresh...")

            await asyncio.gather(
                bot.start(),
                token_refresher_loop(),
                asyncio.sleep(float('inf'))
            )
        except KeyboardInterrupt:
            logger.info("[run] KeyboardInterrupt received. Shutting down...")
            bot.shutdown_event.set()
            logger.info("[run] Shutdown initiated.")
        except Exception as e:
            logger.error(f"Error in controller run: {e}")
            raise