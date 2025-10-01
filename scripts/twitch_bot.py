import asyncio
import random
from dotenv import load_dotenv

from gpt_utils import generate_response
from tts_utils import speak_from_prompt

# === Load environment variables ===
load_dotenv()

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Bot")

class Bot:
    """
    Asynchronous bot that generates speech monologues and listens for input concurrently.
    Manages startup, shutdown, and control of background tasks.
    """
    def __init__(self):
        self.monologue_task = None
        self.input_listener_task = None
        self.tasks = []
        self.shutdown_event = asyncio.Event()
        self.monologue_running = True

        self.starters = [
            "I was just thinking about",
            "Did you know that",
            "It's funny how",
            "Sometimes I wonder if",
            "Have you ever noticed",
            "Let me tell you about"
        ]

    async def start(self):
        """
        Starts the bot: speaks an intro, launches background tasks, and waits for shutdown signal.
        """
        logger.info("[Start] Starting up...")
        
        intro_prompt = "[Start]  Write a short, cheerful greeting..."
        logger.debug(f"[Start] Intro prompt: {intro_prompt}")
        intro_text = generate_response(intro_prompt)
        logger.info(f"[Start] Intro response: {intro_text}")
        await speak_from_prompt(intro_text)

        logger.info("[Start] Launching background tasks...")
        self.tasks.append(asyncio.create_task(self.monologue_loop()))
        self.tasks.append(asyncio.create_task(self.input_listener_loop()))

        await self.shutdown_event.wait()

        logger.info("[Start] Shutdown signal received. Cancelling tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("[Start] All tasks cancelled. Exiting.")

    async def monologue_loop(self):
        """
        Continuously generates and speaks monologues based on starter prompts until cancelled or paused.
        """
        try:
            while True:
                if not self.monologue_running:
                    logger.debug("[Monologue] Monologue paused: Sleeping.")
                    await asyncio.sleep(1) 
                    continue

                logger.debug("[Monologue] Starting new cycle")
                starter_prompt = random.choice(self.starters)
                logger.info(f"[Monologue] Prompt: {starter_prompt}")

                loop = asyncio.get_running_loop()
                try:
                    response = await loop.run_in_executor(None, generate_response, starter_prompt)
                except Exception as e:
                    logger.error(f"[Monologue] Error during response generation: {e}")
                    response = "Something went wrong!"

                logger.info(f"[Monologue] Response:\n{response}")
                await speak_from_prompt(response)

                delay = 10
                logger.debug(f"[Monologue] Waiting {delay} seconds before next cycle...")
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.warning("[Monologue] Monologue loop cancelled")

    def pause_monologue(self):
        """
        Pauses the monologue loop.
        """
        self.monologue_running = False
        logger.info("[Monologue] Paused.")

    def resume_monologue(self):
        """
        Resumes the monologue loop.
        """
        self.monologue_running = True
        logger.info("[Monologue] Resumed.")

    async def input_listener_loop(self):
        """
        Placeholder async loop for listening to user input (e.g., chat), runs until cancelled.
        """
        try:
            while True:
                # pholder 4 twitch chat
                await asyncio.sleep(1)
        except asyncio.CancelledError:
                logger.warning("[Input] Listener loop cancelled")

    def stop(self):
        """
        Signals the bot to shutdown by setting the shutdown event.
        """
        logger.warning("[Stop] Stop signal issued.")
        self.shutdown_event.set()