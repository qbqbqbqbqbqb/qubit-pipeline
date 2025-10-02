import random
import asyncio
from dialogue_model_utils import generate_response
from bot_utils import is_fallback_text
from pathlib import Path

from bot_utils import load_config, load_banned_words

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("MonologueManager")

class MonologueManager:
    def __init__(self, prompt_manager, speech_queue, banned_words_checker, starters=None):
        """
        Handles the monologue generation loop.

        Args:
            prompt_manager: object with method build_prompt(base_prompt)
            speech_queue: asyncio.Queue to send speech text to
            banned_words_checker: callable(text) -> bool to check banned words
            starters: list of strings to start monologues with
        """
        self.prompt_manager = prompt_manager
        self.speech_queue = speech_queue
        self.contains_banned_words = banned_words_checker
        self.monologue_running = True
        self.starters = starters or [
            "I was just thinking about",
            "Did you know that",
            "It's funny how",
            "Sometimes I wonder if",
            "Have you ever noticed",
            "Let me tell you about"
        ]
        self.task = None
        self.cancel_event = asyncio.Event()

        this_file = Path(__file__).resolve()
        project_root = this_file.parent.parent  
        self._root = project_root

        cfg = load_config(self._root, "config.json")
        banned = cfg.get("banned_words_file", "banned_words.txt")

        self.banned_words_path = (self._root / banned).resolve()
        self.banned_words = load_banned_words(self.banned_words_path)


    async def start(self):
        """
        Start the monologue background task.
        """
        self.cancel_event.clear()
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        """
        Stop the monologue background task.
        """
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("[stop] Monologue task cancelled successfully")
            self.task = None
        self.cancel_event.set()

    async def pause(self):
        """
        Pause monologue generation.
        """
        self.monologue_running = False
        logger.info("[pause] Monologue paused")

    async def resume(self):
        """
        Resume monologue generation.
        """
        self.monologue_running = True
        logger.info("[resume] Monologue resumed")

    async def run(self):
        try:
            while True:
                if not self.monologue_running:
                    logger.debug("[run] Monologue paused: Sleeping.")
                    await asyncio.sleep(1)
                    continue

                starter_prompt = random.choice(self.starters)
                logger.info(f"[run] Prompt: {starter_prompt}")

                prompt = self.prompt_manager.build_prompt(base_prompt=starter_prompt)

                loop = asyncio.get_running_loop()
                max_attempts = 2
                response = ""

                for attempt in range(max_attempts):
                    try:
                        response = await loop.run_in_executor(None, generate_response, prompt)
                        logger.info(f"[run] Monologue response (attempt {attempt+1}): {response}")

                        if not response.strip() or is_fallback_text(response):
                            logger.warning(f"[run] Invalid response on attempt {attempt+1}")
                            continue
                        break
                    except Exception as e:
                        logger.error(f"[run] Error generating monologue response: {e}")
                        response = "Something went wrong!"
                        break

                if not response.strip():
                    logger.warning("[run] Skipping empty or invalid response")
                    await asyncio.sleep(5)
                    continue

                logger.info(f"[run] Response:\n{response}")

                if self.contains_banned_words(response, banned_words=self.banned_words):
                    logger.warning(f"[run] Blocked response due to banned words:\n{response}")
                    continue

                await self.speech_queue.put({"type": "monologue", "text": response})

                delay = 5
                logger.debug(f"[run] Waiting {delay} seconds before next cycle...")
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("[run] Monologue task cancelled")
