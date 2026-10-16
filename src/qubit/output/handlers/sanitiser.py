"""
<summary>
DialogueSanitiser — validates and cleans generated response text before output.
</summary>
<remarks>
Applied by OutputCoordinator before any text enters the output queue. Removes
banned words, speaker-name prefixes, and leading punctuation from generated responses.
</remarks>
"""

import re
import string
from typing import Any

from config.config import BOT_NAME
from src.qubit.utils.log_utils import get_logger
from src.qubit.utils.filter_utils import filter_banned_words

logger = get_logger("output_sanitiser")


class DialogueSanitiser:
    """
    <summary>
    Validates and cleans generated response strings.
    Used exclusively by OutputCoordinator before text is queued for output.
    </summary>
    """

    def __init__(self: Any, blacklist: list[str], whitelist: list[str] = None):
        """
        <summary>Initialise the sanitiser with word filter lists.</summary>
        <param name="blacklist">Banned word list — responses containing these are filtered.</param>
        <param name="whitelist">Words that override the blacklist. Defaults to an empty list.</param>
        """
        self.bot_name = BOT_NAME.lower()
        self.blacklist = blacklist
        self.whitelist = whitelist or []

    def is_valid(self, response: str) -> tuple[bool, str]:
        """
        <summary>
        Check whether the response is non-empty and passes the banned-word filter.
        </summary>
        <param name="response">The raw generated response string.</param>
        <returns>
        A (is_valid, filtered_response) tuple. is_valid is False for blank responses.
        The filtered_response has banned words removed regardless.
        </returns>
        """
        if not response.strip():
            return False, response
        filtered = filter_banned_words(response, self.blacklist, self.whitelist)
        return True, filtered

    def remove_trailing_text(self: Any, response: str) -> str:
        """
        <summary>Trim text after the final sentence-ending punctuation (., !, ?).</summary>
        <param name="response">The response string to trim.</param>
        <returns>The response truncated at the last sentence boundary.</returns>
        """
        match = re.search(r"[.!?](?!.*[.!?])", response)
        return response[:match.end()].strip() if match else response.strip()

    def remove_bot_name(self: Any, response: str) -> str:
        """
        <summary>
        Remove leading speaker-name prefixes from the response.
        Recognised prefixes: the bot name (from config), 'assistant', 'user'.
        </summary>
        <param name="response">The response string to strip prefixes from.</param>
        <returns>The response with any leading speaker prefix removed.</returns>
        """
        for prefix in [self.bot_name, "assistant", "user"]:
            if response.lower().startswith(f"{prefix}:"):
                response = response[len(f"{prefix}:"):].lstrip()
        return response

    def strip_leading_punctuation(self: Any, text: str) -> str:
        """
        <summary>Remove leading punctuation characters and whitespace from text.</summary>
        <param name="text">Input text to clean.</param>
        <returns>Text with leading punctuation and spaces removed.</returns>
        """
        i = 0
        while i < len(text) and text[i] in string.punctuation + " ":
            i += 1
        return text[i:]
