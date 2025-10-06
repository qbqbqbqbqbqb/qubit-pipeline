import time
import asyncio
from scripts.bot.bot_utils import contains_banned_words, is_fallback_text

from scripts.utils.log_utils import get_logger
logger = get_logger("MessageManager")

class MessageManager:
    """
    Handles processing of incoming Twitch chat messages and AI response generation.

    This class manages the complete message processing pipeline: receiving chat messages,
    filtering inappropriate content, generating contextual AI responses using memory and
    conversation history, and queuing responses for text-to-speech output.

    Key Features:
    - Message validation against banned words and content filters
    - Memory integration for contextual responses
    - User profile tracking and relationship scoring
    - Queue management for speech synthesis
    - Automatic conversation logging to ChromaDB
    """

    def __init__(self,
                 prompt_manager,
                 queue_manager,
                 banned_words,
                 response_generator,
                 memory_manager=None,
                 bot=None):
        """
        Initialize the message manager with required components.

        Args:
            prompt_manager: Manager for building AI prompts with context
            queue_manager: Queue system for managing speech synthesis tasks
            banned_words: List of words/content to filter out
            response_generator: AI response generator for chat replies
            memory_manager: Memory system for context and logging (optional)
            bot: Reference to the main bot instance (optional)
        """
        self.prompt_manager = prompt_manager
        self.queue_manager = queue_manager
        self.banned_words = banned_words
        self.response_generator = response_generator
        self.memory_manager = memory_manager
        self.bot = bot

    async def process_message(self, message_data):
        """
        Process a single incoming Twitch chat message and generate AI response.

        This method handles the complete message processing pipeline:
        - Validates message freshness (drops messages older than 5 minutes)
        - Filters out messages with banned words
        - Updates user profiles for relationship tracking
        - Generates contextual AI response using memory and conversation history
        - Queues both the original message and AI response for TTS
        - Logs conversation to ChromaDB for future memory retrieval

        Args:
            message_data: Dictionary containing 'message' object and optional 'timestamp'
        """
        try:
            message = message_data["message"]
            timestamp = message_data.get("timestamp", time.time())
            age = time.time() - timestamp

            author = message.author.name
            content = message.content

            if age > 300:
                logger.info(f"Dropped stale message from {author} ({int(age)}s old)")
                return

            if contains_banned_words(content.lower(), banned_words=self.banned_words):
                logger.warning(f"[Filter] Blocked user message with banned words: {content}")
                return

            if self.memory_manager:
                self.memory_manager.update_user_profile(author, username=author)

            if contains_banned_words(author.lower(), banned_words=self.banned_words):
                message_author = "Censored Name"
                user_record = f"Censored Name: {content}"
                base_prompt = f"A user with a censored name said: \"{content}\". Respond to this Twitch chat message."
            else:
                message_author = author
                user_record = f"{author}: {content}"
                base_prompt = f"A user named {author} said: \"{content}\". Respond to this Twitch chat message."

            memory_context = ""
            if self.memory_manager:
                memory_context = self.memory_manager.get_memory_context(user_id=author, current_topic=content)

            prompt = self.prompt_manager.build_prompt(
                base_prompt=base_prompt,
                memory_context=memory_context,
                user_id=author
            )

            loop = asyncio.get_running_loop()
            response = await self.response_generator.generate_response_safely(prompt)

            if is_fallback_text(response):
                logger.warning(f"[process_message] Skipping fallback response: {response}")
                return

            if contains_banned_words(response, banned_words=self.banned_words):
                logger.warning(f"[process_message] Response contains banned words, skipping speech.")
                return

            await self.queue_manager.enqueue_chat({
                "type": "chat_message",
                "text": f"{message_author} said {content}"
            })
            await self.queue_manager.enqueue_chat({
                "type": "chat_response",
                "text": response
            })

            self.prompt_manager.add_user(user_record)
            self.prompt_manager.add_bot(response)

            if self.memory_manager:
                self.memory_manager.add_chat_message("user", content, author)
                self.memory_manager.add_chat_message("assistant", response, self.bot.nick if self.bot else None)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
