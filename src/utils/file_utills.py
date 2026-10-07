from pathlib import Path
import re
import json

from src.utils.log_utils import get_logger
logger = get_logger("File_Utils")

def load_text_file(path: Path) -> str:
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
    return (root / filename).resolve()

def get_root() -> Path:
    this_file = Path(__file__).resolve()
    return this_file.parent.parent.parent

def load_word_list(path: Path) -> list[str]:

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