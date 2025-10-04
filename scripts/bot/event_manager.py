import asyncio
import time
import random
from twitchio.ext import commands

from scripts.bot.bot_utils import is_fallback_text
from scripts.llm.tts_utils import speak_from_prompt
from scripts.core.queue_manager import QueueManager
from scripts.llm.response_gen import ResponseGen

# === Setup colorlog logger ===
from scripts.io.log_utils import get_logger
logger = get_logger("EventManager")

IGNORED_USERS = ['nightbot', 'streamelements']

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TWITCH_STREAMER_NAME = os.getenv("TWITCH_STREAMER_NAME")
TWITCH_BOT_NAME = os.getenv("TWITCH_BOT_NAME")

class EventManager():
    """
    Manages Twitch chat events and bot lifecycle events such as ready, message handling, and command processing.
    Handles filtering of messages, queuing chat messages for TTS response, and managing bot control commands.
    """
    def __init__(self, 
                 bot,
                 queue_manager: QueueManager,
                 response_generator: ResponseGen):
        self.bot = bot
        self.queue_manager = queue_manager
        self.response_generator = response_generator
        self.unprocessed_message_queue = queue_manager.unprocessed_message_queue

        self._startup_done = True

    async def on_ready(self):
        """
        Called when the bot is ready. Speaks an intro message once.
        """
        if self._startup_done:
            return

        logger.info(f"[event_ready] Logged in as {self.bot.nick}")

        intro_prompt = (
            "Write a short, cheerful greeting to welcome viewers to the stream. "
            "Let's have some fun!'"
        )

        self.bot.prompt_manager.add_user(f"System: {intro_prompt}")
        prompt = self.bot.prompt_manager.build_prompt(base_prompt=intro_prompt)

        loop = asyncio.get_running_loop()
        response = ""

        for attempt in range(3):
            try:
                response = await self.response_generator.generate_response_safely(prompt)
                if not response.strip() or is_fallback_text(response):
                    logger.warning(f"[event_ready] Invalid intro response on attempt {attempt+1}")
                    continue
                break
            except Exception as e:
                logger.exception("[event_ready] Error during intro generation", exc_info=e)
                response = "I'm Qubit. This is my stream"
                break

        if not response.strip():
            response = "I'm Qubit. This is my stream"

        await speak_from_prompt(response)
        self.bot.prompt_manager.add_bot(response)

        self._startup_done = True


    def is_streamer_or_bot(self, author: str) -> bool:
        """
        Checks if a given username corresponds to the streamer or the bot itself.
        """
        return (
            author.lower() == TWITCH_STREAMER_NAME.lower()
            or author.lower() == TWITCH_BOT_NAME.lower()
        )
    
    def should_ignore_message(self, message) -> bool:
        """
        Determines if an incoming Twitch chat message should be ignored based on
        author, content, or bot state.
        """
        author = message.author.name
        content = message.content.strip()

        if self.bot.shutting_down:
            logger.info(f"[event_message] Ignored message from {author} (shutting down).")
            return True

        if message.echo and not content.startswith("!"):
            return True

        if author.lower() in IGNORED_USERS:
            return True

        if content.startswith("@"):
            return True
        
        if content.startswith("!") and not self.is_streamer_or_bot():
            return True

        min_length = 2
        word_count = len(content.strip().split())
        if word_count < min_length:
            logger.info(f"[event_message] Ignored short message from {author}: {content}")
            return True

        return False

    async def handle_command(self, cmd: str, message) -> bool:
        """
        Handles bot control commands (!pause, !resume, !stop) if they exist.
        Returns True if a command was handled.
        """
        handled = False

        if cmd == "!pause":
            if callable(self.bot.pause_monologue):
                await self.bot.pause_monologue(message)
            else:
                logger.error(f"[event_message] pause_monologue is not callable: {self.bot.pause_monologue}")
            handled = True

        elif cmd == "!resume":
            if callable(self.bot.resume_monologue):
                await self.bot.resume_monologue(message)
            else:
                logger.error(f"[event_message] resume_monologue is not callable: {self.bot.resume_monologue}")
            handled = True

        elif cmd == "!stop":
            if callable(self.bot.stop):
                await self.bot.stop()
            else:
                logger.error(f"[event_message] stop is not callable: {self.bot.stop}")
            handled = True

        return handled

    async def queue_message(self, message):
        """
        Queues a chat message for processing and response generation with a probabilistic chance.
        """
        author = message.author.name
        response_chance = 1

        if random.random() < response_chance:
            try:
                logger.info(f"[event_message] Queuing message from {author} for response.")
                message_data = {
                    "message": message,
                    "timestamp": time.time()
                }
                await self.unprocessed_message_queue.put(message_data)
            except asyncio.QueueFull:
                logger.warning("[event_message] Queue full. Dropping message.")
        else:
            logger.info(f"[event_message] Ignoring message from {author} (chance).")
