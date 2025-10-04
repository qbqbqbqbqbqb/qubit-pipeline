

from twitchio.ext import commands
print(f"[DEBUG] Using base class: {commands.Bot}")
import asyncio
from queue import Empty

from tts_utils import speak_from_prompt
from prompt_manager import PromptManager
from monologue_manager import MonologueManager
from event_manager import EventManager
from config_manager import ConfigManager
from message_manager import MessageManager
from speech_manager import SpeechManager
from task_manager import TaskManager
from response_gen import ResponseGen
from model_manager import ModelManager

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TWITCH_OAUTH_TOKEN = os.getenv("TWITCH_OAUTH_TOKEN")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")

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

        self.shutdown_event = asyncio.Event()
        self.startup_done = False
        self.monologue_running = True

        self.message_queue = asyncio.Queue(maxsize=50)
        self.speech_queue = asyncio.Queue()

        self.config = ConfigManager()
        self.task_manager = TaskManager()
        
        self.prompt_manager = PromptManager(
            system_instructions = self.config.instructions,
            max_history = self.config.max_chat_history
        )

        self.speech_manager = SpeechManager(
            speech_queue=self.speech_queue,
            banned_words=self.config.banned_words
        )

        self.model_manager = ModelManager()

        self.response_generator = ResponseGen(
            model_manager=self.model_manager
        )

        self.monologue_manager = MonologueManager(
            prompt_manager=self.prompt_manager,
            speech_queue=self.speech_queue,
            response_generator=self.response_generator,
            starters_file=self.config.starters_path
        )

        self.event_manager = EventManager(bot=self,
                                          response_generator=self.response_generator)
        
        self.message_manager = MessageManager(
            prompt_manager=self.prompt_manager,
            speech_queue=self.speech_queue,
            banned_words=self.config.banned_words,
            response_generator=self.response_generator            
        )

        self.shutting_down = False

    # === Bot Controls ===
    async def event_ready(self):
        """
        Called when the bot connects to Twitch and is ready.
        """
        await self.event_manager.on_ready()
        
        self.startup_done = True
        await self.background_tasks()

    async def background_tasks(self):
        """
        Launches background tasks, and waits for shutdown signal.
        """
        logger.info("[Start] Launching background tasks...")
        await self.monologue_manager.start()
        self.task_manager.add_task(self.process_messages())
        self.task_manager.add_task(self.speech_manager.consume())

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
            except Empty:
                break

        logger.info(f"[Stop] Cleared {cleared_messages} items from message queue.")

        cleared_speech = 0
        new_speech_queue = asyncio.Queue()
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
                cleared_speech += 1
            except Empty:
                break

        self.speech_queue = new_speech_queue
        logger.info(f"[Stop] Cleared {cleared_speech} items from speech queue.")

        try:
            ending_prompt = "This is the last thing you will say before the stream ends. Say a short, vtuber-esque sign-off to say goodbye to your audience."
            logger.debug(f"[Stop] Ending prompt: {ending_prompt}")
            
            prompt = self.prompt_manager.build_prompt(base_prompt=ending_prompt)
            end_txt = await self.response_generator.generate_response_safely(prompt)

            logger.info(f"[Stop] Sign-off message: {end_txt}")
            await speak_from_prompt(end_txt)
        except Exception as e:
            logger.error(f"[Stop] Error during shutdown message: {e}")

        await self.task_manager.cancel_all()
        self.shutdown_event.set()

    # === Message Functionality ===
    async def process_messages(self) -> None:
        """
        Continuously processes messages from the message queue by generating TTS responses.
        """
        try:
            while True:
                message_data = await self.message_queue.get()
                await self.message_manager.process_message(message_data)
                self.message_queue.task_done()
        except asyncio.CancelledError:
            logger.info("process_messages task cancelled")
            raise

    async def event_message(self, message):
        """
        Called when any message is received in chat.
        """
        if self.event_manager.should_ignore_message(message):
            return

        author = message.author.name
        content = message.content.strip()

        logger.info(f"[event_message] Message from {author}: {content}")

        if self.event_manager.is_streamer_or_bot(author):
            if await self.event_manager.handle_command(content.lower(), message):
                return

        await self.event_manager.queue_message(message)

    # === Monologue Functionality ===
    async def pause_monologue(self, message):
        """
        Pauses the monologue loop and clears pending speech items to stop ongoing speech.
        """
        await self.monologue_manager.pause()
        await self.speech_manager.pause()
        await message.channel.send("Monologue paused.")
        logger.info("[Monologue] Paused.")

    async def resume_monologue(self, message):
        """
        Resumes the monologue loop.
        """
        await self.monologue_manager.resume()
        await self.speech_manager.resume()
        await message.channel.send("Monologue resumed.")
        logger.info("[Monologue] Resumed.")