import asyncio
import time
import random

from scripts.bot.bot_utils import is_fallback_text
from scripts.io.tts_utils import speak_from_prompt

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("EventManager")

IGNORED_USERS = ['nightbot', 'streamelements']

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TWITCH_STREAMER_NAME = os.getenv("TWITCH_STREAMER_NAME")
TWITCH_BOT_NAME = os.getenv("TWITCH_BOT_NAME")

class EventManager:
    """
    Manages Twitch chat events and bot lifecycle events such as ready, message handling, and command processing.
    Handles filtering of messages, queuing chat messages for TTS response, and managing bot control commands.
    
    Attributes:
        bot (commands.Bot): Reference to the main Twitch bot instance.
    """
    def __init__(self, 
                 bot,
                 response_generator):
        self.bot = bot
        self.response_generator = response_generator

    async def on_ready(self):
        """
        Called when the bot is ready. Speaks an intro message once.
        """
        if self.bot.startup_done:
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

        if content.startswith("!") and not self.is_streamer_or_bot(author):
            return True

        min_length = 2
        word_count = len(content.strip().split())
        if not content.startswith("!") and word_count < min_length:
            logger.info(f"[event_message] Ignored short message from {author}: {content}")
            return True

        return False

    def is_streamer_or_bot(self, author: str) -> bool:
        """
        Checks if a given username corresponds to the streamer or the bot itself.
        """
        return (
            author.lower() == TWITCH_STREAMER_NAME.lower()
            or author.lower() == TWITCH_BOT_NAME.lower()
        )

    async def handle_command(self, cmd: str, message) -> bool:
        """
        Handles bot control commands (!pause, !resume, !stop) if they exist.
        Returns True if a command was handled.
        """
        try:
            handled = False

            if cmd == "!pause":
                if callable(self.bot.pause_monologue):
                    await self.bot.pause_monologue()
                else:
                    logger.error(f"[event_message] pause_monologue is not callable: {self.bot.pause_monologue}")
                handled = True

            elif cmd == "!resume":
                if callable(self.bot.resume_monologue):
                    await self.bot.resume_monologue()
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
        except Exception as e:
            logger.error(f"Error handling command {cmd}: {e}")
            return False


    async def handle_subscription(self, user: str, plan: str):
        """
        Handles subscription events from the Twitch client.
        Generates an AI response to thank the subscriber.
        """
        try:
            logger.info(f"[event_sub] New subscriber: {user} (plan: {plan})")

            sub_prompt = f"A user named {user} just subscribed to the channel with plan {plan}! Write a short, excited thank you message welcoming them as a subscriber."

            response = await self.response_generator.generate_response_safely([{"role": "user", "content": sub_prompt}])

            if response and not is_fallback_text(response):
                await self.bot.queue_manager.enqueue_chat({
                    "type": "sub_response",
                    "text": response
                })

                if self.bot.memory_manager:
                    self.bot.memory_manager.add_chat_message("assistant", response, self.bot.twitch_client.channel_name,
                                                           metadata={"type": "sub_response"})

                logger.info(f"[event_sub] Queued subscription response for {user}")
            else:
                logger.warning(f"[event_sub] Failed to generate subscription response for {user}")

        except Exception as e:
            logger.error(f"[event_sub] Error handling subscription event: {e}")

    async def handle_raid(self, raider: str, viewers: int):
        """
        Handles raid events from the Twitch client.
        Generates an AI response to welcome the raiding channel.
        """
        try:
            logger.info(f"[event_raid] Raid from {raider} with {viewers} viewers")

            raid_prompt = f"Channel {raider} just raided with {viewers} viewers! Write a short, excited welcome message thanking them and greeting their viewers."

            response = await self.response_generator.generate_response_safely([{"role": "user", "content": raid_prompt}])

            if response and not is_fallback_text(response):
                await self.bot.queue_manager.enqueue_chat({
                    "type": "raid_response",
                    "text": response
                })

                if self.bot.memory_manager:
                    self.bot.memory_manager.add_chat_message("assistant", response, self.bot.twitch_client.channel_name,
                                                           metadata={"type": "raid_response"})

                logger.info(f"[event_raid] Queued raid response for {raider}")
            else:
                logger.warning(f"[event_raid] Failed to generate raid response for {raider}")

        except Exception as e:
            logger.error(f"[event_raid] Error handling raid event: {e}")

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
                await self.bot.unprocessed_message_queue.put(message_data)
            except asyncio.QueueFull:
                logger.warning("[event_message] Queue full. Dropping message.")
        else:
            logger.info(f"[event_message] Ignoring message from {author} (chance).")
