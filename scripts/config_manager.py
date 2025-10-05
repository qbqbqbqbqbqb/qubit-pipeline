from bot_utils import (
    load_file, load_banned_words, get_file_path, get_root,
    contains_banned_words, is_fallback_text, load_config
)

from log_utils import get_logger
logger = get_logger("ConfigManager")

class ConfigManager:
    def __init__(self):
        root = get_root()
        cfg = load_config(root, "config.json")

        self.instructions_path = get_file_path(cfg, root, "instructions_file", "instructions.txt")
        self.banned_words_path = get_file_path(cfg, root, "banned_words_file", "banned_words.txt")
        self.starters_path = get_file_path(cfg, root, "starters_file", "starters.txt")
        self.max_chat_history = cfg.get("max_chat_history", 8)

        self.banned_words = load_banned_words(self.banned_words_path)
        self.instructions = load_file(self.instructions_path)
