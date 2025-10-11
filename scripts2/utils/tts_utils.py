"""
This module provides utility functions for normalizing and processing text for text-to-speech (TTS) systems.

It includes functions to remove unsupported characters, convert numbers to words, spell out acronyms,
and perform other transformations to improve TTS pronunciation and clarity.
"""

import re
import inflect
p = inflect.engine()
from scripts2.config.config import ACRONYMS_LIST

def normalise_text_for_tts(text: str) -> str:
    """
    Normalizes the input text for TTS by applying a series of transformations including
    removing brackets, unsupported characters, quotes, converting numbers to words, spelling
    out acronyms, replacing ellipses, and normalizing whitespace.

    Args:
        text (str): The input text to normalize.

    Returns:
        str: The normalized text suitable for TTS.
    """
    text = remove_brackets_and_parentheses(text)
    text = remove_unsupported_chars(text)
    text = remove_quotes(text)
    text = convert_numbers_to_words(text, p.number_to_words)
    text = spell_out_acronyms(text, ACRONYMS_LIST)
    text = replace_ellipses(text)
    text = remove_consecutive_whitespace(text)

    return text

def spell_out_acronyms(text: str, acronyms: list[str]) -> str:
    """
    Replaces known acronyms with their spelled-out versions for clearer TTS pronunciation.

    Args:
        text (str): The input text containing acronyms.
        acronyms (list[str]): List of acronyms to spell out.

    Returns:
        str: The text with acronyms spelled out.
    """
    for acronym in acronyms:
        text = re.sub(
            r'\b' + re.escape(acronym) + r'\b', 
            ' '.join(acronym), 
            text, 
            flags=re.IGNORECASE
        )
    return text

def replace_ellipses(text: str) -> str:
    """
    Replaces ellipses (...) and Unicode ellipsis (…) with a verbal filler phrase.

    Args:
        text (str): The input text containing ellipses.

    Returns:
        str: The text with ellipses replaced by 'dot dot dot'.
    """
    text = text.replace('…', ' dot dot dot ')
    return re.sub(r'\.\.\.+', ' dot dot dot ', text)

def remove_quotes(text: str) -> str:
    """
    Removes quotation marks from the text, including straight and curly quotes.

    Args:
        text (str): The input text containing quotes.

    Returns:
        str: The text with quotes removed and stripped of whitespace.
    """
    text = re.sub(r'[\"“”]', '', text)
    return text.strip()

def remove_consecutive_whitespace(text: str) -> str:
    """
    Removes consecutive whitespace characters and strips leading/trailing spaces.

    Args:
        text (str): The input text.

    Returns:
        str: The text with normalized whitespace.
    """
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def remove_unsupported_chars(text: str) -> str:
    """
    Removes emojis and special Unicode characters not in the ASCII range.

    Args:
        text (str): The input text.

    Returns:
        str: The text with unsupported characters removed and stripped.
    """
    return re.sub(r'[^\x00-\x7F]+', '', text).strip()

def remove_brackets_and_parentheses(text: str) -> str:
    """
    Removes content within square brackets and parentheses, including the brackets themselves.

    Args:
        text (str): The input text.

    Returns:
        str: The text with brackets and parentheses removed and stripped.
    """
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    return text.strip()

def convert_numbers_to_words(text: str, converter) -> str:
    """
    Converts standalone digit sequences to their word equivalents using the provided converter function.

    Args:
        text (str): Input text containing numbers.
        converter (callable): Function to convert numbers to words (e.g., inflect.engine().number_to_words).

    Returns:
        str: The text with numbers converted to words.
    """
    def replace_numbers(match):
        return converter(match.group(0))
    return re.sub(r'\b\d+\b', replace_numbers, text)
