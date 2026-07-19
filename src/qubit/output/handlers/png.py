import asyncio
import json
from pathlib import Path
import httpx

from src.utils.log_utils import get_logger
logger = get_logger("PNGOutputHandler")

class PNGOutputHandler:

    def __init__(self, frontend_url: str = "http://127.0.0.1:8000"):
        self.frontend_url = frontend_url
        self.folder_path = Path("/data/png_models")
        self.processed_folders = {}
        self.current_idle = None
        self.current_speak = None
        self.current_model = None
        self.connected = False
        self.client = httpx.AsyncClient(timeout=5.0)
        self.logger = logger

    async def connect(self) -> None:
        """Process local models and verify frontend is reachable."""
        await self.process_folders()
        self.connected = True
        self.logger.info("PNGOutputHandler connected. Available models: %s", 
                   list(self.processed_folders.keys()))

    async def load_model(self, folder_name: str) -> bool:
        if folder_name not in self.processed_folders:
            self.logger.error("Model folder '%s' not found.", folder_name)
            return False

        data = self.processed_folders[folder_name]
        self.current_idle = data["idle"]
        self.current_speak = data["speak"]
        self.current_model = data["idle"]

        await self._send_command("load_model", {"folder": folder_name})
        self.logger.info("Loaded PNG model: %s", folder_name)
        return True

    async def speak(self) -> None:
        if self.current_speak and self.current_model != self.current_speak:
            self.current_model = self.current_speak
            await self._send_command("speak")

    async def idle(self) -> None:
        if self.current_idle and self.current_model != self.current_idle:
            self.current_model = self.current_idle
            await self._send_command("idle")

    async def _send_command(self, action: str, payload: dict = None):
        """Send command to frontend web server."""
        if not self.connected:
            return

        try:
            data = {"action": action, **(payload or {})}
            await self.client.post(f"{self.frontend_url}/png/command", json=data)
        except Exception as e:
            self.logger.warning("Failed to send command to PNG frontend: %s", e)

    async def process_folders(self) -> None:
        self.processed_folders = {}
        if not self.folder_path.exists():
            self.logger.error("Base folder path does not exist: %s", self.folder_path)
            return

        subdirectories = [d for d in self.folder_path.iterdir() if d.is_dir()]
        for folder in subdirectories:
            try:
                image_files = self.retrieve_image_files(folder)
                idle_images, speak_images = self.filter_and_validate_images(folder, image_files)
                self.save_processed_folder(folder, idle_images, speak_images, image_files)
            except (FileNotFoundError, ValueError) as e:
                self.logger.error("Error processing folder '%s': %s", folder.name, e)
                continue 

    def retrieve_image_files(self, folder: Path) -> list:
        all_files = [f for f in folder.iterdir() if f.is_file()]
        image_files = [f for f in all_files if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.gif']]
        if not image_files:
            raise FileNotFoundError(f"No image files found in '{folder.name}'.")
        return image_files

    def filter_and_validate_images(self, folder: Path, image_files: list) -> tuple:
        idle_images = [f for f in image_files if f.stem.lower().endswith('_idle')]
        speak_images = [f for f in image_files if f.stem.lower().endswith('_speak')]
        if len(idle_images) > 1:
            raise ValueError(f"Validation Error in '{folder.name}': Please ensure there is only 1 '_idle' image.")
        if len(speak_images) > 1:
            raise ValueError(f"Validation Error in '{folder.name}': Please ensure there is only 1 '_speak' image.")
        return idle_images, speak_images

    def save_processed_folder(self, folder: Path, idle_images: list, speak_images: list, image_files: list) -> None:
        self.processed_folders[folder.name] = {
            "idle": idle_images[0] if idle_images else None,
            "speak": speak_images[0] if speak_images else None,
            "all_images": image_files
        }