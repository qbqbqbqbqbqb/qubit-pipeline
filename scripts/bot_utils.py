import re
import json
from pathlib import Path

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Bot")

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

def load_banned_words(path: Path) -> list[str]:
    """
    Loads a list of banned words from a text file, one word per line.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        return [w.strip().lower() for w in lines if w.strip()]
    except Exception as e:
        logger.error(f"Error loading banned words from {path}: {e}")
        return []
        
def contains_banned_words(text: str, banned_words: list[str]) -> bool:
    """
    Checks if the given text contains any banned words as whole words,
    ignoring case and avoiding partial matches.
    """
    text_lower = text.lower()

    for word in banned_words:
        pattern = r'\b' + re.escape(word) + r'\b'

        if re.search(pattern, text_lower):
            return True

    return False

def is_fallback_text(text: str) -> bool:
    text_lower = text.strip().lower()
    return text_lower.startswith("sorry, i couldn't generate a response") or "something went wrong" in text_lower

