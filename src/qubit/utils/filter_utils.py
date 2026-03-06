import difflib
from pathlib import Path
import re
from src.utils.log_utils import get_logger
from config.config import BOT_NAME

logger = get_logger("Filter_Utils")

"""
Filter utilities module for text processing.

This module provides functions to filter and check text for banned words using
blacklists and whitelists. It supports case-insensitive matching and partial
word filtering with options to replace or detect prohibited content.

Functions:
    contains_banned_words: Check if text contains any banned words.
    filter_banned_words: Replace banned words in text with [filtered].
"""


def contains_banned_words(text: str, blacklist: list[str], whitelist: list[str] = None) -> bool:
    """
    Check if the given text contains any banned words from the blacklist.

    This function performs case-insensitive substring matching to detect banned
    words in the text. It ignores words that contain any whitelisted substrings
    to allow for exceptions.

    Args:
        text (str): The input text to check for banned words.
        blacklist (list[str]): A list of banned words to check against.
        whitelist (list[str], optional): A list of whitelisted substrings that
            can override banned words. Defaults to None.

    Returns:
        bool: True if any banned word is found (and not whitelisted), False otherwise.

    Example:
        >>> contains_banned_words("Hello badword", ["bad"])
        True
        >>> contains_banned_words("Hello badword", ["bad"], ["badword"])
        False
    """
    banned_set = set(word.lower() for word in blacklist)
    whitelist_set = set(word.lower() for word in whitelist or [])
    words_in_text = re.findall(r'\S+', text.lower())

    for word in words_in_text:
        clean_word = re.sub(r'^\W+|\W+$', '', word)
        if any(whitelisted in clean_word for whitelisted in whitelist_set):
            continue

        for banned in banned_set:
            if banned in clean_word:
                return True
    return False

def filter_banned_words(text: str, blacklist: list[str], whitelist: list[str] = None) -> str:
    """
    Replace banned words in the text with '[filtered]'.

    This function filters out banned words by replacing them with a placeholder
    string. It supports whitelisting to prevent filtering of allowed substrings.
    The replacement is case-insensitive and preserves punctuation.

    Args:
        text (str): The input text to filter.
        blacklist (list[str]): A list of banned words to replace.
        whitelist (list[str], optional): A list of whitelisted substrings that
            should not be filtered. Defaults to None.

    Returns:
        str: The filtered text with banned words replaced by '[filtered]'.

    Example:
        >>> filter_banned_words("Hello badword!", ["bad"])
        "Hello [filtered]!"
        >>> filter_banned_words("Hello badword!", ["bad"], ["badword"])
        "Hello badword!"
    """
    banned_set = set(word.lower() for word in blacklist)
    whitelist_set = set(word.lower() for word in whitelist or [])

    def replace_banned_in_word(word: str) -> str:
        if word.lower() == '[filtered]':
            return word

        clean_word = re.sub(r'[^\w]', '', word.lower())
        if any(whitelisted in clean_word for whitelisted in whitelist_set):
            return word

        for banned in banned_set:
            if banned in clean_word:
                pattern = re.compile(re.escape(banned), re.IGNORECASE)
                word = pattern.sub('[filtered]', word)
        return word

    tokens = re.findall(r'\w+|\W+', text)
    return ''.join(replace_banned_in_word(token) for token in tokens)


