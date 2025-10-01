from twitchio.ext import commands
import asyncio
import random
import re

from gpt_utils import generate_response
from tts_utils import speak_from_prompt

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
        self.tasks = []
        self.shutdown_event = asyncio.Event()
        self.startup_done = False
        self.monologue_running = True

        self.message_queue = asyncio.Queue()
        self.speech_queue = asyncio.Queue()
        self.processing_message = False

        self.prompt_template = self.load_file("instructions.txt")
        self.banned_words = self.load_banned_words("banned_words.txt")

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

        intro_prompt = "[Start]  This is the first thing you will say this stream. Write a short, cheerful greeting to welcome viewers to the stream. For example: 'Hey everyone! Welcome to the Qubit stream! I'm so excited to hang out with you all today. Let's have some fun!'"
        logger.debug(f"[Start] Intro prompt: {intro_prompt}")

        loop = asyncio.get_running_loop()
        prompt = self.build_prompt(intro_prompt)
        intro_text = await loop.run_in_executor(None, generate_response, prompt)
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
            author = message.author.name

            logger.info(f"[Twitch] Generating response to: {message_content}")

            try:
                message_content = message.content
                if self.contains_banned_words(message_content.lower()):
                    logger.warning(f"[Filter] Blocked user message with banned words: {message_content}")
                    continue

                if self.contains_banned_words(author.lower()):
                    await self.speech_queue.put({"type": "chat_response", "text": f"A censored name says {message_content}"})
                else:
                    await self.speech_queue.put({"type": "chat_response", "text": f"{message.author.name} says {message_content}"})
                
                loop = asyncio.get_running_loop()
                
                if self.contains_banned_words(author.lower()):
                    prompt = self.build_prompt(
                        f"A user with a censored name said: \"{message_content}\". Respond to this Twitch chat message."
                    )
                else:
                    prompt = self.build_prompt(
                        f"A user named {message.author.name} said: \"{message_content}\". Respond to this Twitch chat message."
                    )

                response = await loop.run_in_executor(None, generate_response, prompt)

                if self.contains_banned_words(response):
                    logger.warning(f"[Filter] Response contains banned words, skipping speech: {response}")
                    response = "I'm sorry, I can't respond to that."

                #await message.channel.send("response generated, speaking now...")
                await self.speech_queue.put({"type": "chat_response", "text": response})
            except Exception as e:
                logger.error(f"Error processing message: {e}")
            finally:
                self.speech_queue.task_done()

    async def event_message(self, message):
        """
        Handles incoming Twitch chat messages.
        """
        content = message.content
        author = message.author.name

        if message.echo and not content.startswith("!"):
            return
        
        if author.lower() in IGNORED_USERS:
            return
        
        logger.info(f"[Twitch] Message from {author}: {content}")

        if (author.lower() == TWITCH_STREAMER_NAME.lower() or
            author.lower() == TWITCH_BOT_NAME.lower()):
            if content.lower() == "!pause":
                await self.pause_monologue(message)
                return
            
            if content.lower() == "!resume":
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
                prompt = self.build_prompt(starter_prompt)
                loop = asyncio.get_running_loop()

                try:
                    response = await loop.run_in_executor(None, generate_response, prompt)
                except Exception as e:
                    logger.error(f"[Monologue] Error during response generation: {e}")
                    response = "Something went wrong!"

                logger.info(f"[Monologue] Response:\n{response}")
                if self.contains_banned_words(response):
                    logger.warning(f"[Filter] Blocked response due to banned words:\n{response}")
                    continue

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
                    if self.contains_banned_words(text):
                        logger.warning(f"[Speech Filter] Blocked TTS due to banned content:\n{text}")
                        continue
                    await speak_from_prompt(text)

            except Exception as e:
                logger.error(f"Error during speech playback: {e}")
            finally:
                self.speech_queue.task_done()

    # === Heh.... Prompt Engineering... ===
    def build_prompt(self, base_prompt: str, mood: str = "energetic", 
                     interaction_level: str = "high",
                     tone: str = "casual and humorous"
                     ) -> str:
        """
        Wraps a base prompt with instructions to generate a lively,
        fun, casual Twitch streamer style response.
        """

        interaction_instruction = {
            "low": "Focus mostly on monologue style, little audience interaction.",
            "medium": "Engage with the audience occasionally, reacting to chat.",
            "high": "Frequently interact with the audience, asking questions, "
                    "responding to chat, and making jokes about chat messages."
        }.get(interaction_level, "Frequently interact with the audience.")


        instructions =  self.prompt_template.format(
            mood=mood,
            tone=tone,
            interaction_instruction=interaction_instruction
        )

        prompt = f"{instructions} Now talk about: {base_prompt}"

        return prompt

    def load_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()

    def load_banned_words(self, path: str) -> list:
        try:
            with open(path, "r", encoding="utf-8") as file:
                words = [line.strip().lower() for line in file if line.strip()]
            return words
        except Exception as e:
            logger.error(f"Error loading banned words from {path}: {e}")
            return []
        
    # == Moderation ===
    def contains_banned_words(self, text: str) -> bool:
        """
        Checks if the given text contains any banned words as whole words,
        ignoring case and avoiding partial matches.
        """
        text_lower = text.lower()

        for word in self.banned_words:
            pattern = r'\b' + re.escape(word) + r'\b'

            if re.search(pattern, text_lower):
                return True

        return False

