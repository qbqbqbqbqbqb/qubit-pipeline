import time
import asyncio
from scripts.bot.bot_utils import contains_banned_words, is_fallback_text

from scripts.utils.log_utils import get_logger
logger = get_logger("MessageManager")

class MessageManager:
    def __init__(self,
                 prompt_manager,
                 queue_manager,
                 banned_words,
                 response_generator,
                 memory_manager=None,
                 bot=None):
        self.prompt_manager = prompt_manager
        self.queue_manager = queue_manager
        self.banned_words = banned_words
        self.response_generator = response_generator
        self.memory_manager = memory_manager
        self.bot = bot

    async def process_message(self, message_data):
        """
        Process a single chat message: generate a response and queue speech.
        Filters out banned words and fallback responses.
        """
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

        try:
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

            # Add to persistent memory
            if self.memory_manager:
                self.memory_manager.add_chat_message("user", content, author)
                self.memory_manager.add_chat_message("assistant", response, self.bot.nick if self.bot else None)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
