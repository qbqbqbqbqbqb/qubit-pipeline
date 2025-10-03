import random
import asyncio
from pathlib import Path

from dialogue_model_utils import generate_response
from bot_utils import (
    is_fallback_text, load_config, load_banned_words, 
    get_file_path, get_root, contains_banned_words
)

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("MonologueManager")

class MonologueManager:
    def __init__(self, prompt_manager, speech_queue, starters=None):
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

        root = get_root()
        cfg = load_config(root, "config.json")

        banned_words_path = get_file_path(cfg, root, "banned_words_file", "banned_words.txt")
        self.banned_words = load_banned_words(banned_words_path)
        
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

    async def start(self):
        """
        Start the monologue background task.
        """
        self.monologue_running = True
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
        """
        Main loop that generates monologues continuously while running.

        It waits if paused, builds prompts, generates responses with retries,
        validates responses against banned words and fallback text,
        queues valid responses to the speech queue, and waits between cycles.

        Handles task cancellation gracefully.
        """
        try:
            while True:
                if not self.monologue_running:
                    logger.debug("[run] Monologue paused: Sleeping.")
                    await asyncio.sleep(1)
                    continue

                starter_prompt = self._choose_starter_prompt()
                prompt = self.prompt_manager.build_prompt(base_prompt=starter_prompt)

                response = await self._generate_response_with_retries(prompt)

                if not self._is_valid_response(response):
                    logger.warning("[run] Invalid or banned response, skipping.")
                    await asyncio.sleep(5)
                    continue

                await self._queue_response(response)

                await self._wait_between_monologues()
        except asyncio.CancelledError:
            logger.info("[run] Monologue task cancelled")

    def _choose_starter_prompt(self) -> str:
        """
        Selects and returns a random starter prompt from the available starters.
        """        
        choice = random.choice(self.starters)
        logger.info(f"[run] Selected starter prompt: {choice}")
        return choice

    async def _generate_response_with_retries(self, prompt: str, max_attempts: int = 2) -> str:
        """
        Generate a response from the dialogue model, retrying up to max_attempts times if invalid.

        """        
        loop = asyncio.get_running_loop()
        response = ""
        for attempt in range(max_attempts):
            try:
                response = await loop.run_in_executor(None, generate_response, prompt)
                logger.info(f"[run] Generated response (attempt {attempt + 1}): {response}")

                if not response.strip() or is_fallback_text(response):
                    logger.warning(f"[run] Response invalid on attempt {attempt + 1}")
                    continue
                return response
            except Exception as e:
                logger.error(f"[run] Error generating response on attempt {attempt + 1}: {e}")
                return "Something went wrong!"
        return response

    def _is_valid_response(self, response: str) -> bool:
        """
        Check whether the generated response is valid.

        Validity checks include:
        - Response is not empty or whitespace only.
        - Response is not fallback text.
        - Response does not contain banned words.
        """
        if not response.strip():
            logger.warning("[run] Empty response")
            return False
        if is_fallback_text(response):
            logger.warning("[run] Fallback text detected")
            return False
        if contains_banned_words(response, banned_words=self.banned_words):
            logger.warning(f"[run] Banned words found in response: {response}")
            return False
        return True

    async def _queue_response(self, response: str):
        """
        Adds the given response to the queue.
        """
        await self.speech_queue.put({"type": "monologue", "text": response})
        logger.info("[run] Response queued to speech queue")

    async def _wait_between_monologues(self, delay: int = 5):
        """
        Wait for a specified delay before generating the next monologue.
        """
        logger.debug(f"[run] Waiting {delay} seconds before next monologue")
        await asyncio.sleep(delay)
