from pathlib import Path
import re
import json

from scripts2.utils.log_utils import get_logger
logger = get_logger("File_Utils")

"""
File utility functions for loading, checking, and processing various file types.

This module contains helper functions to handle common file operations such as reading text and JSON files,
verifying file existence, resolving paths, and loading lists of words or phrases from files.
"""

# Is this the best way of doing this? I don't know.
# It's python so I also don't really care.
# Can we move all ML-relevant libraries to a language I like more please?

def load_text_file(path: Path) -> str:
    """
    Loads and returns the content of a text file as a string.

    Args:
        path (Path): The path to the text file to load.

    Returns:
        str: The content of the file.

    Raises:
        Exception: If the file cannot be read, re-raises the exception after logging.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not load file {path}: {e}")
        raise

def load_json_file(path: str) -> dict:
    """
    Loads a JSON file and returns its content as a dictionary.

    Args:
        path (str): The file path to the JSON file.

    Returns:
        dict: The parsed JSON data.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def check_file_exists(path: Path) -> bool:
    """
    Checks if a file exists at the given path.

    Args:
        path (Path): The path to check for existence.

    Returns:
        bool: True if the file exists and path is not None, False otherwise.
    """
    if not path or not path.exists():
        logger.warning(f"File {path} does not exist or is None")
        return False
    return True

def get_file_path(root: Path, filename: str) -> Path:
    """
    Constructs and returns a fully resolved file path by joining the root path with the filename.

    Args:
        root (Path): The root directory path.
        filename (str): The filename to append to the root.

    Returns:
        Path: The resolved full path.
    """
    return (root / filename).resolve()

def get_root() -> Path:
    """
    Determines and returns the project root directory path.

    This function uses the current file's path to navigate up the directory tree.

    Returns:
        Path: The path to the project root directory.
    """
    this_file = Path(__file__).resolve()
    return this_file.parent.parent.parent

def load_word_list(path: Path) -> list[str]:
    """
    Loads a list of words from a text file, one word per line.

    Cleans words by keeping only alphabetic characters and converting to lowercase.
    Skips empty lines and invalid words.

    Args:
        path (Path): The path to the text file containing words.

    Returns:
        list[str]: A list of cleaned words. Returns an empty list if the file does not exist or an error occurs.
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

    Args:
        path (Path): The path to the text file containing phrases.

    Returns:
        list[str]: A list of phrases. Returns an empty list if the file does not exist or an error occurs.
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