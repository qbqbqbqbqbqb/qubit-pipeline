import random
import asyncio
import time
from pathlib import Path

from scripts.llm.response_gen import ResponseGen

from scripts.bot.bot_utils import (
    is_fallback_text, contains_banned_words
)
from scripts.config.config_manager import ConfigManager
from scripts.bot.queue_manager import Queue

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("MonologueManager")


class MonologueManager:
    """
    Manages AI monologue generation for VTuber stream conversations.

    This class continuously generates contextual monologue responses based on
    conversation starters and current memory context. It handles the full
    monologue pipeline: prompt generation, AI response creation, content
    validation, and speech queue management.

    Key Features:
    - Continuous monologue generation with configurable delays
    - Content validation against banned words and quality filters
    - Memory integration for contextual responses
    - Queue management with monologue limits
    - Automatic ChromaDB storage of generated monologues
    """

    def __init__(self,
                 prompt_manager,
                 monologue_queue: Queue,
                 response_generator: ResponseGen,
                 starters_file: Path = None,
                 memory_manager=None,
                 ):
        """
        Initialize the monologue manager with required components.

        Args:
            prompt_manager: Prompt manager with build_prompt() method for context generation
            monologue_queue: Queue for sending generated speech text to TTS system
            response_generator: AI response generator for monologue creation
            starters_file: Path to file containing monologue starter phrases (optional)
            memory_manager: MemoryManager for context and conversation logging
        """
        self.prompt_manager = prompt_manager

        self.response_generator = response_generator
        self.config = ConfigManager()
        self.memory_manager = memory_manager

        self.monologue_running = True

        if isinstance(monologue_queue, Queue):
                self.monologue_queue = monologue_queue
        else:
                self.monologue_queue = Queue(maxsize=0, cap=None)

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
        logger.debug(f"[run] Queue size: {self.monologue_queue.qsize()}, monologue_running={self.monologue_running}")

        try:
            while True:
                if not self.monologue_running:
                    logger.debug("[run] Monologue paused: Sleeping.")
                    await asyncio.sleep(1)
                    continue
                
                logger.debug(f"[run] Queue size: {self.monologue_queue.qsize()}, monologue_running={self.monologue_running}")
                starter_prompt = self._choose_starter_prompt()

                memory_context = ""
                if self.memory_manager:
                    memory_context = self.memory_manager.get_memory_context()

                prompt = self.prompt_manager.build_prompt(
                    base_prompt=starter_prompt,
                    memory_context=memory_context
                )

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
        Selects and returns a random starter prompt from available monologue starters.

        Uses the configured starters file or falls back to default prompts.
        Logged for debugging monologue generation flow.
        """
        choice = random.choice(self.starters)
        logger.info(f"[_choose_starter_prompt] Selected starter prompt: {choice}")
        return choice

    async def _generate_response_with_retries(self, prompt) -> str:
        """
        Generate AI response with error handling and retries.

        Attempts to generate a monologue response using the AI response generator.
        Falls back to a generic error message if generation fails.

        Args:
            prompt: The formatted prompt for monologue generation

        Returns:
            Generated monologue text or fallback error message
        """
        try:
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
        Queue the generated monologue for speech synthesis and memory storage.

        Manages monologue queue limits, sends response to TTS system,
        and logs the monologue to ChromaDB conversation collection
        for memory and retrieval purposes.

        Args:
            response: The generated monologue text to queue
        """
        try:
            temp_items = []
            monologue_count = 0

            MAX_MONOLOGUES = 5

            while monologue_count >= MAX_MONOLOGUES:
                logger.info(f"[_queue_response] Monologue limit hit ({monologue_count}), removing oldest monologue(s)")
                new_temp = []
                removed = 0

                for item in temp_items:
                    if removed < (monologue_count - MAX_MONOLOGUES + 1):
                        removed +=1
                        continue
                    new_temp.append(item)
                temp_items = new_temp

            final_queue = []
            for i, item in enumerate(temp_items):
                final_queue.append(item)

            for item in final_queue:
                await self.monologue_queue.put(item)

            logger.debug(f"[_queue_response] Queueing monologue: {response}")
            logger.debug(f"[_queue_response] Queue size before put: {self.monologue_queue.qsize()}")

            await self.monologue_queue.put({"type": "monologue", "text": response})
            logger.debug(
                f"[_queue_response] Queue size after put: {self.monologue_queue.qsize()}")

            if self.memory_manager:
                monologue_id = f"mono_{int(time.time())}_{hash(response) % 10000}"
                self.memory_manager.conversation_collection.upsert(
                    ids=[monologue_id],
                    documents=[response],
                    metadatas=[{
                        "content": response,
                        "timestamp": time.time(),
                        "type": "monologue"
                    }]
                )
                self.memory_manager.add_chat_message("assistant", response, user_id=None, metadata={"type": "monologue"})

            logger.info("[run] Response queued to speech queue")
        except Exception as e:
            logger.error(f"Error queueing response: {e}")

    async def _wait_between_monologues(self, delay: int = 5):
        """
        Wait for a specified delay before generating the next monologue.
        """
        logger.debug(f"[run] Waiting {delay} seconds before next monologue")
        await asyncio.sleep(delay)
