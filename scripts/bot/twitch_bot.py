

from typing import Any
import asyncio
from queue import Empty
from datetime import datetime

from scripts.bot.twitch_client import TwitchClient
from scripts.io.tts_utils import speak_from_prompt
from scripts.llm.prompt_manager import PromptManager
from scripts.io.monologue_manager import MonologueManager
from scripts.bot.event_manager import EventManager
from scripts.config.config_manager import ConfigManager
from scripts.bot.message_manager import MessageManager
from scripts.io.speech_manager import SpeechManager
from scripts.core.task_manager import TaskManager
from scripts.llm.response_gen import ResponseGen
from scripts.llm.model_manager import ModelManager
from scripts.bot.queue_manager import Queue, QueueManager

# === Load environment variables ===
import os
from dotenv import load_dotenv
load_dotenv()

TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("Bot")

async def dump_queue_sizes(bot):
    while not bot.shutdown_event.is_set():
        logger.debug(
            f"[QUEUE DUMP] msg:{bot.queue_manager.message_queue.qsize()} "
            f"mono:{bot.queue_manager.monologue_queue.qsize()} "
            f"speech:{bot.queue_manager.speech_queue.qsize()}"
        )
        await asyncio.sleep(2)

class Bot:
    """
    VTuber AI Twitch bot with real-time conversation and monologue generation.

    This bot connects to Twitch chat using direct API calls and performs several key functions:
    - Generates AI-powered monologue speech based on conversation starters
    - Responds to user chat messages with contextual AI replies
    - Manages memory of conversations with automatic cleanup (1-minute decay)
    - Handles TTS (Text-to-Speech) for voice output
    - Processes commands from streamers/moderators
    - Maintains persistent user profiles and semantic memory

    The bot uses ChromaDB for fast conversation storage and JSON files for
    long-term user data and semantic knowledge. All conversations automatically
    expire after 1 minute to prevent memory bloat during long streams.
    """

    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.startup_done = False
        self.monologue_running = True

        self.unprocessed_message_queue = Queue(maxsize=50)
        self.queue_manager = QueueManager(unprocessed_message_queue=self.unprocessed_message_queue)

        self.config = ConfigManager()
        self.task_manager = TaskManager()

        self.prompt_manager = PromptManager(
            system_instructions=self.config.instructions,
            max_history=self.config.max_chat_history
        )

        self.speech_manager = SpeechManager(
            speech_queue=self.queue_manager.speech_queue,
            banned_words=self.config.banned_words
        )

        self.model_manager = ModelManager()

        self.response_generator = ResponseGen(
            model_manager=self.model_manager
        )

        from scripts.memory_manager import MemoryManager
        self.memory_manager = MemoryManager(response_generator=self.response_generator)

        self.monologue_manager = MonologueManager(
            prompt_manager=self.prompt_manager,
            monologue_queue=self.queue_manager.monologue_queue,
            response_generator=self.response_generator,
            starters_file=self.config.starters_path,
            memory_manager=self.memory_manager
        )

        self.twitch_client = TwitchClient(
            config=self.config,
            message_handler=self._handle_chat_message,
            event_handler=self._handle_event
        )

        self.event_manager = EventManager(
            bot=self,
            response_generator=self.response_generator
        )

        self.message_manager = MessageManager(
            prompt_manager=self.prompt_manager,
            queue_manager=self.queue_manager,
            banned_words=self.config.banned_words,
            response_generator=self.response_generator,
            memory_manager=self.memory_manager,
            bot=self
        )

        self.shutting_down = False
        self.nick = os.getenv("TWITCH_BOT_NAME", "qubit_tan") 

    # === Bot Controls ===
    async def start(self):
        """
        Start the bot by connecting to Twitch and launching background tasks.
        """
        logger.info("[Bot] Starting VTuber AI Twitch bot...")

        if not await self.twitch_client.connect():
            logger.error("[Bot] Failed to connect to Twitch. Exiting.")
            return

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
        self.task_manager.add_task(self.queue_manager.merge_queues())
        self.task_manager.add_task(dump_queue_sizes(self))
        self.task_manager.add_task(self.memory_cleanup_task())
        await self.shutdown_event.wait()

        await self._perform_graceful_shutdown()

    # === Message and Event Handlers ===
    async def _handle_chat_message(self, author: str, content: str, timestamp: datetime):
        """
        Handle incoming chat messages from the Twitch client.
        """
        try:
            class MockMessage:
                def __init__(self, author_name, content_text, msg_timestamp):
                    self.author = type('Author', (), {'name': author_name})()
                    self.content = content_text
                    self.timestamp = msg_timestamp
                    self.echo = False

            message = MockMessage(author, content, timestamp)

            if self.event_manager.should_ignore_message(message):
                return

            logger.info(f"[event_message] Message from {author}: {content}")

            if self.event_manager.is_streamer_or_bot(author):
                if await self.event_manager.handle_command(content.lower(), message):
                    return

            await self.event_manager.queue_message(message)
        except Exception as e:
            logger.error(f"Error handling chat message from {author}: {e}")

    async def _handle_event(self, event_data: dict):
        """
        Handle EventSub events from the Twitch client.
        """
        try:
            event_type = event_data.get('type')
            logger.info(f"[EventSub] Received event: {event_type}")

            if event_type == 'subscription':
                user = event_data.get('user', 'unknown')
                plan = event_data.get('plan', 'unknown')
                await self.event_manager.handle_subscription(user, plan)

            elif event_type == 'raid':
                raider = event_data.get('raider', 'unknown')
                viewers = event_data.get('viewers', 0)
                await self.event_manager.handle_raid(raider, viewers)
        except Exception as e:
            logger.error(f"Error handling event {event_data}: {e}")

    # === Message sending ===
    async def send_message(self, message: str):
        """
        Send a message to the Twitch channel.
        """
        try:
            await self.twitch_client.send_message(message)
        except Exception as e:
            logger.error(f"Error sending message '{message}': {e}")

    async def _perform_graceful_shutdown(self) -> None:
        """
        Performs a graceful shutdown sequence with proper error handling and cleanup.

        This method ensures all background tasks are cancelled, resources are released,
        and the bot shuts down cleanly even if individual components fail.
        """
        logger.info("[Shutdown] Initiating graceful shutdown sequence...")

        shutdown_errors = []

        try:
            logger.info("[Shutdown] Cancelling background tasks...")
            await self.task_manager.cancel_all()
            logger.info("[Shutdown] All background tasks cancelled successfully")

        except Exception as e:
            error_msg = f"[Shutdown] Error cancelling tasks: {e}"
            logger.error(error_msg)
            shutdown_errors.append(error_msg)

        try:
            logger.info("[Shutdown] Stopping monologue manager...")
            await self.monologue_manager.stop()
            logger.info("[Shutdown] Monologue manager stopped successfully")

        except Exception as e:
            error_msg = f"[Shutdown] Error stopping monologue manager: {e}"
            logger.error(error_msg)
            shutdown_errors.append(error_msg)

        if shutdown_errors:
            logger.warning(f"[Shutdown] Completed with {len(shutdown_errors)} errors: {shutdown_errors}")
        else:
            logger.info("[Shutdown] All shutdown operations completed successfully")

    async def stop(self):
        """
        Signals the bot to shutdown by speaking a sign-off message and setting the shutdown event.
        """
        logger.warning("[Stop] Stop signal issued.")

        self.shutting_down = True
        self.monologue_running = False
        self.monologue_manager.monologue_running = False

        if self.monologue_manager.task:
            self.monologue_manager.task.cancel()

        cleared = await self.queue_manager.clear_all()

        logger.info("[Stop] About to speak sign-off message")

        end_txt = "Goodbye everyone! Thanks for watching. This is Qubit signing off!"
        logger.info(f"[Stop] Sign-off message: {end_txt}")
        try:
            asyncio.create_task(speak_from_prompt(end_txt))
            import time
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"[Stop] Error during shutdown message: {e}")

        import os
        os._exit(0)

    # === Message Functionality ===
    async def process_messages(self) -> None:
        """
        Continuously processes incoming chat messages from the message queue.

        This background task runs indefinitely, pulling messages from the
        unprocessed_message_queue and passing them to the message_manager
        for AI response generation and TTS processing.
        """
        try:
            while True:
                try:
                    message_data = await self.unprocessed_message_queue.get()
                    await self.message_manager.process_message(message_data)
                    self.unprocessed_message_queue.task_done()
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except asyncio.CancelledError:
            logger.info("process_messages task cancelled")
            raise


    # === Monologue Functionality ===
    async def pause_monologue(self):
        """
        Pauses the monologue loop and clears pending speech items to stop ongoing speech.
        """
        await self.monologue_manager.pause()
        await self.speech_manager.pause()
        await self.send_message("Monologue paused.")
        logger.info("[Monologue] Paused.")

    async def memory_cleanup_task(self):
        """
        Background task that periodically cleans up old memories and decayed conversations.

        Runs every 60 seconds to:
        - Remove old semantic memories from JSON files
        - Clean up conversations older than 1 minute from ChromaDB
        - Maintain memory system health during long streams
        """
        while not self.shutdown_event.is_set():
            try:
                self.memory_manager.cleanup_old_memories()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error during memory cleanup: {e}")
                await asyncio.sleep(60)

    async def resume_monologue(self):
        """
        Resumes the monologue loop.
        """
        await self.monologue_manager.resume()
        await self.speech_manager.resume()
        await self.send_message("Monologue resumed.")
        logger.info("[Monologue] Resumed.")