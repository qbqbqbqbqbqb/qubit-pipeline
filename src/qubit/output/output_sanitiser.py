import re
import string

from src.qubit.utils.log_utils import get_logger
from config.config import BOT_NAME
from src.qubit.utils.filter_utils import filter_banned_words

logger = get_logger("output_sanitiser")

class DialogueSanitiser:
    def __init__(self, bot_name: str, blacklist: list[str], whitelist: list[str] = None):
        self.bot_name = bot_name.lower()
        self.blacklist = blacklist
        self.whitelist = whitelist or []

    def is_valid(self, response: str) -> tuple[bool, str]:
        if not response.strip():
            return False, response
        filtered = filter_banned_words(response, self.blacklist, self.whitelist)
        return True, filtered

    def remove_trailing_text(self, response: str) -> str:
        match = re.search(r'[.!?](?!.*[.!?])', response)
        return response[:match.end()].strip() if match else response.strip()

    def remove_bot_name(self, response: str) -> str:
        for prefix in [self.bot_name, "assistant", "user"]:
            if response.lower().startswith(f"{prefix}:"):
                response = response[len(f"{prefix}:"):].lstrip()
        return response

    def strip_leading_punctuation(self, text: str) -> str:
        i = 0
        while i < len(text) and text[i] in string.punctuation + " ":
            i += 1
        return text[i:]