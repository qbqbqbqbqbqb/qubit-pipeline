import re
import json
from pathlib import Path
import difflib

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("Bot_Utils")

def load_config(root: Path, cfg_name: str) -> dict:
    """
    Loads a JSON configuration file from the specified root directory.
    """
    cfg_path = (root / cfg_name).resolve()
    if not cfg_path.is_file():
        logger.warning(f"Config file not found at {cfg_path}, using defaults.")
        return {}
    try:
        text = cfg_path.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception as e:
        logger.error(f"Error reading config {cfg_path}: {e}")
        return {}

def load_file(path: Path) -> str:
    """
    Loads and returns the content of a text file.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not load file {path}: {e}")
        raise

def get_file_path(cfg: dict, root: Path, config_key: str, default_filename: str) -> Path:
    """
    Returns a resolved file path from config or default.
    """
    filename = cfg.get(config_key, default_filename)
    return (root / filename).resolve()

def get_root() -> Path:
    """
    Gets the project root
    """
    this_file = Path(__file__).resolve()
    return this_file.parent.parent.parent

def load_banned_words(path: Path) -> list[str]:
    """
    Loads a list of banned words from a text file, one word per line.
    Cleans words by keeping only alphabetic characters.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        cleaned_words = []
        for w in lines:
            stripped = w.strip()
            if stripped:
                cleaned = re.sub(r'[^a-zA-Z]', '', stripped.lower())
                if cleaned:
                    cleaned_words.append(cleaned)
        return cleaned_words
    except Exception as e:
        logger.error(f"Error loading banned words from {path}: {e}")
        return []

def contains_banned_words(text: str, banned_words: list[str]) -> bool:
    """
    Checks if the given text contains any banned words, including substrings,
    plurals, and fuzzy matches (similarity > 0.8).
    """
    text_lower = text.lower()
    words_in_text = re.findall(r'\b\w+\b', text_lower)

    for banned in banned_words:
        if banned in text_lower:
            return True

        plural = banned + 's'
        if plural in text_lower:
            return True

        for word in words_in_text:
            similarity = difflib.SequenceMatcher(None, banned, word).ratio()
            if similarity > 0.8 and len(word) >= 3: 
                logger.debug(f"Fuzzy match: '{word}' similar to banned '{banned}' (ratio: {similarity:.2f})")
                return True

    return False

def filter_banned_words(text: str, banned_words: list[str]) -> str:
    """
    Replaces banned words (including substrings, plurals, and fuzzy matches) with [filtered].
    """
    result = text
    banned_set = set(banned_words)

    words_in_text = re.findall(r'\b\w+\b', result)
    for word in words_in_text:
        word_lower = word.lower()
        if word_lower == '[filtered]':
            continue
        replace_whole = False
        for banned in banned_set:
            if banned in word_lower:
                replace_whole = True
                break
            similarity = difflib.SequenceMatcher(None, banned, word_lower).ratio()
            if similarity > 0.7 and len(word) >= 3:
                replace_whole = True
                break
        if replace_whole:
            pattern = r'\b' + re.escape(word) + r'\b'
            result = re.sub(pattern, '[filtered]', result, count=1, flags=re.IGNORECASE)

    sorted_banned = sorted(set(banned_words + [w + 's' for w in banned_words]), key=len, reverse=True)

    for banned in sorted_banned:
        pattern = re.compile(re.escape(banned), re.IGNORECASE)
        result = pattern.sub('[filtered]', result)

    return result

def is_fallback_text(text: str) -> bool:
    text_lower = text.strip().lower()
    return text_lower.startswith("sorry, i couldn't generate a response") or "something went wrong" in text_lower

