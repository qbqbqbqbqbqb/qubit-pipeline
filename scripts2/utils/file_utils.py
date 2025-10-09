from pathlib import Path

from scripts2.utils.log_utils import get_logger
logger = get_logger("File Utils")

# Is this the best way of doing this? I don't know. 
# It's python so I also don't really care. 
# Can we move all ML-relevant libraries to a language I like more please?

def load_file(path: Path) -> str:
    """
    Loads and returns the content of a text file.
    """
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not load file {path}: {e}")
        raise

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