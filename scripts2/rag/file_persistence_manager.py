import json
from pathlib import Path
from typing import Any

from scripts2.modules.base_module import BaseModule


class FilePersistenceManager(BaseModule):
    def __init__(self, base_path: str = "."):
        super().__init__("FilePersistenceManager")
        self.base_path = Path(base_path)

    def save_json(self, file_path: Path, data: Any) -> None:
        """Save data to JSON file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"Error saving {file_path}: {e}")