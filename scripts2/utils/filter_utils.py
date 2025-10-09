import difflib
from pathlib import Path
import re
from scripts.utils.log_utils import get_logger
logger = get_logger("Filter_Utils")

def is_valid_response(response: str, blacklist, whitelist: list[str] = None) -> tuple[bool, str]:
    """
    Check whether the generated response is valid and filter banned words.

    Returns (is_valid, filtered_response)
    """
    if not response.strip():
        logger.warning("[_is_valid_response] Empty response")
        return False, response
    
    filtered = filter_banned_words(text=response, blacklist=blacklist, whitelist=whitelist)
    if filtered != response:
        logger.warning(f"[_is_valid_response] Filtered banned words: {response} -> {filtered}")
    return True, filtered

def contains_banned_words(text: str, blacklist: list[str], whitelist: list[str] = None) -> bool:
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


