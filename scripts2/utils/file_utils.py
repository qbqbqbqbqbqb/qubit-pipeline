from pathlib import Path
import re
import json

from scripts2.utils.log_utils import get_logger
logger = get_logger("File_Utils")

# Is this the best way of doing this? I don't know. 
# It's python so I also don't really care. 
# Can we move all ML-relevant libraries to a language I like more please?

def load_text_file(path: Path) -> str:
    """
    Loads and returns the content of a text file.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not load file {path}: {e}")
        raise

def load_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def check_file_exists(path: Path) -> bool:
    if not path or not path.exists():
        logger.warning(f"File {path} does not exist or is None")
        return False
    return True

def get_file_path(root: Path, filename: str) -> Path:
    """
    Returns a resolved file path.
    """
    return (root / filename).resolve()

def get_root() -> Path:
    """
    Gets the project root
    """
    this_file = Path(__file__).resolve()
    return this_file.parent.parent.parent

def load_word_list(path: Path) -> list[str]:
    """
    Loads a list of words from a text file, one word per line.
    Cleans words by keeping only alphabetic characters.
    """
    if not check_file_exists(path):
        return []

    try:
        content = load_text_file(path)
        lines = content.splitlines()
        cleaned_words = []
        for w in lines:
            stripped = w.strip()
            if stripped:
                cleaned = re.sub(r'[^a-zA-Z]', '', stripped.lower())
                if cleaned:
                    cleaned_words.append(cleaned)
        return cleaned_words
    except Exception as e:
        logger.error(f"Error loading word list from {path}: {e}")
        return []
    
def load_phrases(path: Path) -> list[str]:
    """
    Loads lines from a file as phrases, preserving spacing and punctuation,
    but strips leading/trailing whitespace and skips empty lines.
    """
    if not check_file_exists(path):
        return []

    try:
        content = load_text_file(path)
        lines = content.splitlines()
        phrases = [line.strip() for line in lines if line.strip()]
        logger.info(f"Loaded {len(phrases)} phrases from {path}")
        return phrases
    except Exception as e:
        logger.error(f"Error loading phrases from {path}: {e}")
        return []