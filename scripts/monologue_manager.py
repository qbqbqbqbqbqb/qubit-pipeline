import random
import asyncio
from pathlib import Path

from response_gen import ResponseGen

from bot_utils import (
    is_fallback_text, contains_banned_words
)
from config_manager import ConfigManager

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("MonologueManager")

#MAX_MONOLOGUES = 5

class MonologueManager:
    def __init__(self, 
                 prompt_manager, 
                 speech_queue: asyncio.Queue, 
                 response_generator: ResponseGen,
                 starters_file: Path =None,
                 ):
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
        self.response_generator = response_generator
        self.config = ConfigManager()

        self.monologue_running = True
        if starters_file and starters_file.exists():
            with open(starters_file, "r", encoding="utf-8") as f:
                self.starters = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(self.starters)} starter phrases from {starters_file}")
        else:
            self.starters = starters_file or [
                ""
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

        new_queue = asyncio.Queue()
        while not self.speech_queue.empty():
            try:
                item = self.speech_queue.get_nowait()
                if item["type"] != "monologue":
                    await new_queue.put(item)
                self.speech_queue.task_done()
            except asyncio.QueueEmpty:
                break
        self.speech_queue = new_queue
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
        logger.debug(f"[run] Queue size: {self.speech_queue.qsize()}, monologue_running={self.monologue_running}")

        try:
            while True:
                if not self.monologue_running:
                    logger.debug("[run] Monologue paused: Sleeping.")
                    await asyncio.sleep(1)
                    continue
                
                logger.debug(f"[run] Queue size: {self.speech_queue.qsize()}, monologue_running={self.monologue_running}")
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
        logger.info(f"[_choose_starter_prompt] Selected starter prompt: {choice}")
        return choice

    async def _generate_response_with_retries(self, prompt):
        try:
            # Use await when calling an async method
            response = await self.response_generator.generate_response_safely(prompt)
            return response
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

    async def _queue_response(self, response: str):
        """
        Adds the given response to the queue.
        """
        temp_items = []
        monologue_count = 0

        """         
        while not self.speech_queue.empty():
            item = await self.speech_queue.get()
            if item["type"] == "monologue":
                monologue_count += 1
            temp_items.append(item)

        while monologue_count >= MAX_MONOLOGUES:
            logger.info(f"[_queue_response] Monologue limit hit ({monologue_count}), removing oldest monologue(s)")
            new_temp = []
            removed = 0

            for item in temp_items:
                if item["type"] == "monologue" and removed < (monologue_count - MAX_MONOLOGUES + 1):
                    removed +=1
                    continue
                new_temp.append(item)
            temp_items = new_temp

        inserted = False
        final_queue = []
        for i, item in enumerate(temp_items):
            final_queue.append(item)
            if not inserted and item["type"] == "chat":
                final_queue.append({"type": "monologue", "text": response})          
                inserted = True

        if not inserted:
            final_queue.append({"type": "monologue", "text": response})

        for item in final_queue:
            await self.speech_queue.put(item) """

        logger.debug(f"[_queue_response] Queueing monologue: {response}")
        logger.debug(f"[_queue_response] Queue size before put: {self.speech_queue.qsize()}")

        await self.speech_queue.put({"type": "monologue", "text": response})
        logger.debug(f"[_queue_response] Queue size after put: {self.speech_queue.qsize()}")
        logger.info("[run] Response queued to speech queue")

    async def _wait_between_monologues(self, delay: int = 15):
        """
        Wait for a specified delay before generating the next monologue.
        """
        logger.debug(f"[run] Waiting {delay} seconds before next monologue")
        await asyncio.sleep(delay)
