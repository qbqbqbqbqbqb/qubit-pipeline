"""Dialogue sanitisation utilities.

This module provides the DialogueSanitiser class, which is responsible
for cleaning and validating chatbot responses. It includes functionality
for filtering banned words, removing unwanted prefixes, trimming trailing
text, and stripping leading punctuation.
"""

import re
import string
from typing import Any

from config.config import BOT_NAME
from src.utils.log_utils import get_logger
from src.qubit.utils.filter_utils import filter_banned_words

logger = get_logger("output_sanitiser")


class DialogueSanitiser:
    """Utility class for sanitising chatbot dialogue responses.

    This class provides methods to validate and clean chatbot outputs,
    including removing unwanted prefixes, filtering banned words, and
    trimming unnecessary punctuation or trailing text.
    """

    def __init__(self:Any, blacklist: list[str], whitelist: list[str] = None):
        """Initialise the DialogueSanitiser.

        Args:
            bot_name (str): Name of the bot to strip from responses.
            blacklist (list[str]): List of banned words to filter out.
            whitelist (list[str], optional): List of allowed words that
                bypass filtering. Defaults to None.
        """
        self.bot_name = BOT_NAME.lower()
        self.blacklist = blacklist
        self.whitelist = whitelist or []

    def is_valid(self, response: str) -> tuple[bool, str]:
        """Validate and filter a chatbot response.

        Args:
            response (str): The raw chatbot response.

        Returns:
            tuple[bool, str]: A tuple where the first element indicates
            whether the response is valid (non-empty), and the second
            element is the filtered response.
        """
        if not response.strip():
            return False, response
        filtered = filter_banned_words(response, self.blacklist, self.whitelist)
        return True, filtered

    def remove_trailing_text(self: Any, response: str) -> str:
        """Trim text after the final sentence-ending punctuation.

        Args:
            response (str): The chatbot response.

        Returns:
            str: The response truncated at the last '.', '!', or '?'.
        """
        match = re.search(r'[.!?](?!.*[.!?])', response)
        return response[:match.end()].strip() if match else response.strip()

    def remove_bot_name(self: Any, response: str) -> str:
        """Remove leading bot or speaker name prefixes from response.

        Recognised prefixes include the bot name, 'assistant', and 'user'.

        Args:
            response (str): The chatbot response.

        Returns:
            str: The response without leading speaker prefixes.
        """
        for prefix in [self.bot_name, "assistant", "user"]:
            if response.lower().startswith(f"{prefix}:"):
                response = response[len(f"{prefix}:"):].lstrip()
        return response

    def strip_leading_punctuation(self: Any, text: str) -> str:
        """Remove leading punctuation and whitespace from text.

        Args:
            text (str): Input text to clean.

        Returns:
            str: Text with leading punctuation and spaces removed.
        """
        i = 0
        while i < len(text) and text[i] in string.punctuation + " ":
            i += 1
        return text[i:]
