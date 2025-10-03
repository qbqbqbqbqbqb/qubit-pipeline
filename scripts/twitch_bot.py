from twitchio.ext import commands
import asyncio
import random
import re
import time
import json
from pathlib import Path

from dialogue_model_utils import generate_response
from tts_utils import speak_from_prompt
from prompt_manager import PromptManager
from monologue_manager import MonologueManager
from bot_utils import (
    load_file, load_banned_words, get_file_path, get_root,
    contains_banned_words, is_fallback_text, load_config
)

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TWITCH_OAUTH_TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
TWITCH_STREAMER_NAME = os.getenv("TWITCH_STREAMER_NAME")
TWITCH_BOT_NAME = os.getenv("TWITCH_BOT_NAME")

IGNORED_USERS = ['nightbot', 'streamelements']

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Bot")

class Bot(commands.Bot):
    """
    Asynchronous bot that generates speech monologues and listens for input concurrently.
    Also responds to twitch chat messages.
    Manages startup, shutdown, and control of background tasks.
    """
    def __init__(self):
        super().__init__(
            token=TWITCH_OAUTH_TOKEN,
            prefix="!",
            initial_channels=[TWITCH_CHANNEL]
        )

        root = get_root()
        cfg = load_config(root, "config.json")

        instructions_path = get_file_path(cfg, root, "instructions_file", "instructions.txt")
        banned_words_path = get_file_path(cfg, root, "banned_words_file", "banned_words.txt")

        self.banned_words = load_banned_words(banned_words_path)

        self.tasks = []
        self.shutdown_event = asyncio.Event()
        self.startup_done = False
        self.monologue_running = True

        self.message_queue = asyncio.Queue(maxsize=50)
        self.speech_queue = asyncio.Queue()
        self.processing_message = False
        self.max_chat_history = cfg.get("max_chat_history", 8)

        self.prompt_manager = PromptManager(
            system_instructions = load_file(instructions_path),
            max_history = self.max_chat_history
        )

        self.monologue_manager = MonologueManager(
            prompt_manager=self.prompt_manager,
            speech_queue=self.speech_queue
        )

        self.shutting_down = False

        self.generation_tasks = set()
        
        self.starters = [
            "I was just thinking about",
            "Did you know that",
            "It's funny how",
            "Sometimes I wonder if",
            "Have you ever noticed",
            "Let me tell you about"
        ]

    # === Bot Controls ===
    async def event_ready(self):
        """
        Called when the bot is ready. Speaks an intro message once.
        """
        if self.startup_done:
            return 
        
        logger.info(f"[Twitch] Logged in as {self.nick}")

        intro_prompt = (
            "This is the first thing you will say this stream. "
            "Write a short, cheerful greeting to welcome viewers to the stream. "
            "For example: 'Hey everyone! Welcome to the Qubit stream!"
            "I'm so excited to hang out with you all today. Let's have some fun!'"
        )
        
        logger.debug(f"[event_ready] Intro prompt: {intro_prompt}")

        self.prompt_manager.add_user(f"System: {intro_prompt}")

        prompt = self.prompt_manager.build_prompt(base_prompt=intro_prompt)

        max_attempts = 3
        intro_text = ""

        loop = asyncio.get_running_loop()
        for attempt in range(max_attempts):
            try:
                intro_text = await loop.run_in_executor(None, generate_response, prompt)
                logger.info(f"[event_ready] Intro response (attempt {attempt+1}): {intro_text}")

                if not intro_text.strip() or "couldn't generate" in intro_text.lower() or "something went wrong" in intro_text.lower():
                    logger.warning(f"[event_ready] Invalid intro response on attempt {attempt+1}")
                    continue
                break 
            except Exception as e:
                logger.error(f"[event_ready] Error generating intro response: {e}")
                intro_text = "I'm Qubit. This is my stream"
                break
            
        if not intro_text.strip():
            intro_text = "I'm Qubit. This is my stream"

        await speak_from_prompt(intro_text)

        self.prompt_manager.add_bot(intro_text)

        self.startup_done = True
        await self.background_tasks()

    async def background_tasks(self):
        """
        Launches background tasks, and waits for shutdown signal.
        """
        logger.info("[Start] Launching background tasks...")
        await self.monologue_manager.start()
        self.tasks.append(asyncio.create_task(self.process_messages()))
        self.tasks.append(asyncio.create_task(self.speech_consumer()))

        await self.shutdown_event.wait()

        logger.info("[Start] Shutdown signal received. Cancelling tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.monologue_manager.stop()
        logger.info("[Start] All tasks cancelled. Exiting.")

    async def stop(self):
        """
        Signals the bot to shutdown by speaking a sign-off message and setting the shutdown event.
        """
        logger.warning("[Stop] Stop signal issued.")

        self.shutting_down = True
        self.monologue_running = False

        cleared_messages = 0
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
                self.message_queue.task_done()
                cleared_messages += 1
            except asyncio.QueueEmpty:
                break

        logger.info(f"[Stop] Cleared {cleared_messages} items from message queue.")

        cleared_speech = 0
        new_speech_queue = asyncio.Queue()
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
                cleared_speech += 1
            except asyncio.QueueEmpty:
                break

        self.speech_queue = new_speech_queue
        logger.info(f"[Stop] Cleared {cleared_speech} items from speech queue.")

        try:
            ending_prompt = "This is the last thing you will say before the stream ends. Say a short, vtuber-esque sign-off to say goodbye to your audience."
            logger.debug(f"[Stop] Ending prompt: {ending_prompt}")
            
            prompt = self.build_prompt(ending_prompt)
            loop = asyncio.get_running_loop()
            end_txt = await loop.run_in_executor(None, generate_response, prompt)

            logger.info(f"[Stop] Sign-off message: {end_txt}")
            await speak_from_prompt(end_txt)
        except Exception as e:
            logger.error(f"[Stop] Error during shutdown message: {e}")

        self.shutdown_event.set()

    # === Message Functionality ===
    async def process_messages(self):
        """
        Continuously processes messages from the message queue by generating TTS responses.
        """
        while True:
            message_data = await self.message_queue.get()
            message = message_data["message"]
            timestamp = message_data.get("timestamp", time.time())

            author = message.author.name
            message_content = message.content
            age = time.time() - timestamp

            if age > 120:
                logger.info(f"Dropped stale message from {author} ({int(age)}s old)")
                self.message_queue.task_done()
                continue

            logger.info(f"[process_messages] Generating response to: {message_content}")

            try:
                if contains_banned_words(message_content.lower(), banned_words=self.banned_words):
                    logger.warning(f"[Filter] Blocked user message with banned words: {message_content}")
                    continue
                
                if contains_banned_words(author.lower(), banned_words=self.banned_words):
                    message_author = f"Censored Name"
                    user_record = f"Censored Name: {message_content}"
                    base_prompt = f"A user with a censored name said: \"{message_content}\". Respond to this Twitch chat message."
                else:
                    message_author = f"{author}"
                    user_record = f"{author}: {message_content}"
                    base_prompt = f"A user named {author} said: \"{message_content}\". Respond to this Twitch chat message."

                self.prompt_manager.add_user(user_record)
                prompt = self.prompt_manager.build_prompt(base_prompt=base_prompt)

                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, generate_response, prompt)

                if is_fallback_text(response):
                                    logger.warning(f"[process_messages] Skipping response due to fallback message: {response}")
                                    self.message_queue.task_done()
                                    continue
                                
                if contains_banned_words(response, banned_words=self.banned_words):
                    logger.warning(f"[process_messages] Response contains banned words, skipping speech: {response}")
                    continue

                await self.speech_queue.put({
                    "type": "chat_message",
                    "text": f"{message_author} said {message_content}"
                })
                await self.speech_queue.put({
                    "type": "chat_response", 
                    "text": response
                })

                self.prompt_manager.add_bot(response)
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
            finally:
                self.message_queue.task_done() 


    async def event_message(self, message):
        """
        Handles incoming Twitch chat messages.
        """
        content = message.content
        author = message.author.name

        if self.shutting_down:
            logger.info(f"[Shutdown] Ignored message from {author} because bot is shutting down.")
            return
    
        if message.echo and not content.startswith("!"):
            return
        
        if author.lower() in IGNORED_USERS:
            return
        
        if content.startswith("@"):
            return
        
        min_length = 3
        word_count = len(content.strip().split())
        if word_count < min_length:
            logger.info(f"[Filter] Ignored short message from {author}: {content}")
            return
        
        logger.info(f"[Twitch] Message from {author}: {content}")

        if (author.lower() == TWITCH_STREAMER_NAME.lower() or
            author.lower() == TWITCH_BOT_NAME.lower()):
            if content.lower() == "!pause":
                if callable(self.pause_monologue):
                    await self.pause_monologue(message)
                else:
                    logger.error(f"pause_monologue is not callable: {self.pause_monologue}")
                return
            
            if content.lower() == "!resume":
                if callable(self.resume_monologue):
                    await self.resume_monologue(message)
                else:
                    logger.error(f"resume_monologue is not callable: {self.resume_monologue}")
                return

            if content.lower() == "!stop":
                if callable(self.stop):
                    await self.stop(message)
                else:
                    logger.error(f"stop is not callable: {self.stop}")
                return
            
            if content.lower() == "!stop":
                await self.stop()
                return
        
        response_chance = 0.8

        if random.random() < response_chance:
            try:
                logger.info(f"[Twitch] Queuing message from {author} for response.")
                message_data = {
                    "message": message,
                    "timestamp": time.time()
                }
                await self.message_queue.put(message_data)
            except asyncio.QueueFull:
                logger.warning(f"[Twitch] Queue Full. Dropping message.")
        else:
            logger.info(f"[Twitch] Ignoring message from {author} (chance).")   
            pass

    # === Monologue Functionality ===
    async def pause_monologue(self, message):
        """
        Pauses the monologue loop and clears pending speech items to stop ongoing speech.
        """
        await self.monologue_manager.pause()

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

        await message.channel.send("Monologue paused and speech queue cleared.")
        logger.info("[Monologue] Paused and speech queue cleared.")


    async def resume_monologue(self, message):
        """
        Resumes the monologue loop.
        """
        await self.monologue_manager.resume()
        await message.channel.send("Monologue resumed.")
        logger.info("[Monologue] Resumed.")

    # === Handling Speech Queue ===
    async def speech_consumer(self):
        """
        Continuously consumes text messages from the speech queue and processes them for speech synthesis.
        """
        while True:
            item = await self.speech_queue.get()
            try:
                if item["type"] == "monologue" and not self.monologue_running:
                    logger.debug("[Speech] Monologue paused, skipping speech.")
                else:
                    text = item['text'] 
                    if contains_banned_words(text, banned_words=self.banned_words):
                        logger.warning(f"[Speech Filter] Blocked TTS due to banned content:\n{text}")
                        continue
                    await speak_from_prompt(text)

            except Exception as e:
                logger.error(f"Error during speech playback: {e}")
            finally:
                self.speech_queue.task_done()
