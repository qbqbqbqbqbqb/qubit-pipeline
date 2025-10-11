import json
from pathlib import Path
from typing import Any

from scripts2.modules.base_module import BaseModule


"""Module for persisting data to files, providing JSON serialization functionality."""


class FilePersistenceManager(BaseModule):
    """Handles file-based persistence operations, inheriting from BaseModule for logging and common functionality."""

    def __init__(self, base_path: str = "."):
        """Initialize the FilePersistenceManager with a base path for file operations.

        Args:
            base_path (str): Base directory path. Defaults to "." (current directory).
        """
        super().__init__("FilePersistenceManager")
        self.base_path = Path(base_path)

    def save_json(self, file_path: Path, data: Any) -> None:
        """Save the provided data to a JSON file with proper formatting.

        Args:
            file_path (Path): Path object pointing to the target file.
            data (Any): The data to be serialized to JSON.

        Raises:
            Exception: If an error occurs during file writing or JSON serialization.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"Error saving {file_path}: {e}")