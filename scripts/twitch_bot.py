import os
from twitchio.ext import commands
import asyncio
import random

from gpt_utils import generate_response
from tts_utils import speak_from_prompt

# === Load environment variables ===
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
        self.tasks = []
        self.shutdown_event = asyncio.Event()
        self.startup_done = False
        self.monologue_running = True

        self.message_queue = asyncio.Queue()
        self.speech_queue = asyncio.Queue()
        self.processing_message = False

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

        intro_prompt = "[Start]  Write a short, cheerful greeting..."
        logger.debug(f"[Start] Intro prompt: {intro_prompt}")

        loop = asyncio.get_running_loop()
        intro_text = await loop.run_in_executor(None, generate_response, intro_prompt)
        logger.info(f"[Start] Intro response: {intro_text}")
        await speak_from_prompt(intro_text)

        self.startup_done = True
        await self.background_tasks()

    async def background_tasks(self):
        """
        Launches background tasks, and waits for shutdown signal.
        """
        logger.info("[Start] Launching background tasks...")
        self.tasks.append(asyncio.create_task(self.monologue_loop()))
        self.tasks.append(asyncio.create_task(self.process_messages()))
        self.tasks.append(asyncio.create_task(self.speech_consumer()))

        await self.shutdown_event.wait()

        logger.info("[Start] Shutdown signal received. Cancelling tasks...")
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("[Start] All tasks cancelled. Exiting.")

    def stop(self):
        """
        Signals the bot to shutdown by setting the shutdown event.
        """
        logger.warning("[Stop] Stop signal issued.")
        self.shutdown_event.set()

    # === Message Functionality ===
    async def process_messages(self):
        """
        Continuously processes messages from the message queue by generating TTS responses.
        """
        while True:
            message = await self.message_queue.get()

            try:
                prompt = message.content
                logger.info(f"[Twitch] Generating response to: {prompt}")
                await self.speech_queue.put({"type": "chat_response", "text": "{message.author.name} says {prompt}"})

                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, generate_response, prompt)

                await message.channel.send("response generated, speaking now...")
                await self.speech_queue.put({"type": "chat_response", "text": response})
            except Exception as e:
                logger.error(f"Error processing message: {e}")
            finally:
                self.speech_queue.task_done()

    async def event_message(self, message):
        """
        Handles incoming Twitch chat messages.
        """
        content = message.content.lower()
        if message.echo and not content.startswith("!"):
            return
        
        if message.author.name.lower() in IGNORED_USERS:
            return
        
        logger.info(f"[Twitch] Message from {message.author.name}: {message.content}")

        if (message.author.name.lower() == TWITCH_STREAMER_NAME.lower() or
            message.author.name.lower() == TWITCH_BOT_NAME.lower()):
            if content == "!pause":
                await self.pause_monologue(message)
                return
            
            if content == "!resume":
                await self.resume_monologue(message)
                return

        await self.message_queue.put(message)


    # === Monologue Functionality ===
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
                await self.speech_queue.put({"type": "monologue", "text": response})

                delay = 10
                logger.debug(f"[Monologue] Waiting {delay} seconds before next cycle...")
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.warning("[Monologue] Monologue loop cancelled")

    async def pause_monologue(self, message):
        """
        Pauses the monologue loop and clears pending speech items to stop ongoing speech.
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

        await message.channel.send("Monologue paused and speech queue cleared.")
        logger.info("[Monologue] Paused and speech queue cleared.")


    async def resume_monologue(self, message):
        """
        Resumes the monologue loop.
        """
        self.monologue_running = True
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
                    await speak_from_prompt(text)

            except Exception as e:
                logger.error(f"Error during speech playback: {e}")
            finally:
                self.speech_queue.task_done()
