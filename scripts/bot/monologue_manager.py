import random
import asyncio
from pathlib import Path

from response_gen import ResponseGen

from bot_utils import (
    is_fallback_text, contains_banned_words
)
from config_manager import ConfigManager
from queue_manager import QueueManager

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("MonologueManager")

#MAX_MONOLOGUES = 5

class MonologueManager:
    def __init__(self, 
                 prompt_manager, 
                 queue_manager: QueueManager,
                 response_generator: ResponseGen,
                 starters_file: Path =None,
                 delay: int = 5
                 ):
        """
        Handles the monologue generation loop.

        Args:
            prompt_manager: object with method build_prompt(base_prompt)
            monologue_queue: QueueManager to send speech text to
            banned_words_checker: callable(text) -> bool to check banned words
            starters: list of strings to start monologues with
        """
        self.prompt_manager = prompt_manager
        self.response_generator = response_generator
        self.config = ConfigManager()
        self.monologue_running = True
        self.delay = delay

        self.monologue_queue = queue_manager.monologue_queue

        if starters_file and starters_file.exists():
            with open(starters_file, "r", encoding="utf-8") as f:
                self.starters = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(self.starters)} starter phrases from {starters_file}")
        else:
            self.starters = starters_file or [
                ""
            ]
    
        self.task: asyncio.Task | None = None

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
        await self.monologue_queue.pause()
        logger.info("[pause] Monologue paused")

    async def resume(self):
        """
        Resume monologue generation.
        """        
        self.monologue_running = True
        await self.monologue_queue.resume()
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
        except Exception as e:
            logger.exception(f"f[run] Error: {e}")
            await asyncio.sleep(2)
            await self.run()

    def _choose_starter_prompt(self) -> str:
        """
        Selects and returns a random starter prompt from the available starters.
        """        
        choice = random.choice(self.starters)
        logger.info(f"[_choose_starter_prompt] Selected starter prompt: {choice}")
        return choice

    async def _generate_response_with_retries(self, prompt):
        try:
            return await self.response_generator.generate_response_safely(prompt)
        except Exception as e:
            logger.exception(f"Error in generate response with retries: {e}")
            return "Something went wrong!"

    def _is_valid_response(self, response: str) -> bool:
        """
        Check whether the generated response is valid.

        Validity checks include:
        - Response is not empty or whitespace only.
        - Response is not fallback text.
        - Response does not contain banned words.
        """
        if not response.strip():
            logger.warning("[_is_valid_response] Empty response")
            return False
        if is_fallback_text(response):
            logger.warning("[_is_valid_response] Fallback text detected")
            return False
        if contains_banned_words(response, banned_words=self.config.banned_words):
            logger.warning(f"[_is_valid_response] Banned words found in response: {response}")
            return False
        return True

    async def _queue_response(self, response: str) -> None:
        monologue_item = {"type": "monologue", "text": response}
        await self.monologue_queue.put(monologue_item)
        logger.debug(f"[_queue_response] Queued monologue: {response}")
        logger.debug(f"[_queue_response] Queue size after put: {self.monologue_queue.qsize()}")

    async def _wait_between_monologues(self):
        """
        Wait for a specified delay before generating the next monologue.
        """
        logger.debug(f"[run] Waiting {self.delay} seconds before next monologue")
        await asyncio.sleep(self.delay)
