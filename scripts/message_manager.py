import time
import asyncio
from bot_utils import contains_banned_words, is_fallback_text
from dialogue_model_utils import generate_response

from log_utils import get_logger
logger = get_logger("MessageManager")

class MessageManager:
    def __init__(self, prompt_manager, speech_queue, banned_words):
        self.prompt_manager = prompt_manager
        self.speech_queue = speech_queue
        self.banned_words = banned_words

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

        if age > 120:
            logger.info(f"Dropped stale message from {author} ({int(age)}s old)")
            return

        if contains_banned_words(content.lower(), banned_words=self.banned_words):
            logger.warning(f"[Filter] Blocked user message with banned words: {content}")
            return

        try:
            if contains_banned_words(author.lower(), banned_words=self.banned_words):
                message_author = "Censored Name"
                user_record = f"Censored Name: {content}"
                base_prompt = f"A user with a censored name said: \"{content}\". Respond to this Twitch chat message."
            else:
                message_author = author
                user_record = f"{author}: {content}"
                base_prompt = f"A user named {author} said: \"{content}\". Respond to this Twitch chat message."

            self.prompt_manager.add_user(user_record)
            prompt = self.prompt_manager.build_prompt(base_prompt=base_prompt)

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, generate_response, prompt)

            if is_fallback_text(response):
                logger.warning(f"[process_message] Skipping fallback response: {response}")
                return

            if contains_banned_words(response, banned_words=self.banned_words):
                logger.warning(f"[process_message] Response contains banned words, skipping speech.")
                return

            await self.speech_queue.put({
                "type": "chat_message",
                "text": f"{message_author} said {content}"
            })
            await self.speech_queue.put({
                "type": "chat_response",
                "text": response
            })

            self.prompt_manager.add_bot(response)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
