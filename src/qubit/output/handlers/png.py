"""
<summary>
PNGOutputHandler — drives a PNG avatar model via HTTP commands to the frontend web server.
</summary>
<remarks>
Discovers PNG model folders under /data/png_models at connect time. Each valid model
folder contains exactly one _idle image and exactly one _speak image. Commands (speak,
idle, load_model) are sent as JSON POST requests to the frontend at frontend_url.
</remarks>
"""

import asyncio
from pathlib import Path
import httpx

from src.qubit.utils.log_utils import get_logger

logger = get_logger("PNGOutputHandler")


class PNGOutputHandler:
    """
    <summary>
    Controls a PNG avatar by posting speak/idle/load_model commands to the
    frontend web server. Avatar state is tracked locally to avoid redundant commands.
    </summary>
    """

    def __init__(self, frontend_url: str = "http://127.0.0.1:8000"):
        """
        <summary>Initialise the handler with the frontend server URL.</summary>
        <param name="frontend_url">Base URL of the frontend server that accepts PNG avatar commands.</param>
        """
        self.frontend_url = frontend_url
        self.folder_path = Path("/data/png_models")
        self.processed_folders: dict = {}
        self.current_idle = None
        self.current_speak = None
        self.current_model = None
        self.connected = False
        self.client = httpx.AsyncClient(timeout=5.0)
        self.logger = logger

    async def connect(self) -> None:
        """
        <summary>
        Process local model folders and mark the handler as connected.
        Does not verify that the frontend server is reachable.
        </summary>
        """
        await self.process_folders()
        self.connected = True
        self.logger.info("PNGOutputHandler connected. Available models: %s",
                         list(self.processed_folders.keys()))

    async def load_model(self, folder_name: str) -> bool:
        """
        <summary>
        Set the active model by folder name and notify the frontend.
        </summary>
        <param name="folder_name">The name of the model folder to load.</param>
        <returns>True if the folder exists and the command was sent, False otherwise.</returns>
        """
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
        """
        <summary>Switch to the speak image if not already active.</summary>
        """
        if self.current_speak and self.current_model != self.current_speak:
            self.current_model = self.current_speak
            await self._send_command("speak")

    async def idle(self) -> None:
        """
        <summary>Switch to the idle image if not already active.</summary>
        """
        if self.current_idle and self.current_model != self.current_idle:
            self.current_model = self.current_idle
            await self._send_command("idle")

    async def _send_command(self, action: str, payload: dict = None) -> None:
        """
        <summary>POST a command JSON to the frontend. Silently logs failures.</summary>
        <param name="action">The action string (e.g. 'speak', 'idle', 'load_model').</param>
        <param name="payload">Optional extra fields to include in the request body.</param>
        """
        if not self.connected:
            return

        try:
            data = {"action": action, **(payload or {})}
            await self.client.post(f"{self.frontend_url}/png/command", json=data)
        except Exception as e:
            self.logger.warning("Failed to send command to PNG frontend: %s", e)

    async def process_folders(self) -> None:
        """
        <summary>
        Scan the models directory and populate processed_folders.
        Logs errors for invalid or missing folders without raising.
        </summary>
        """
        self.processed_folders = {}
        if not self.folder_path.exists():
            self.logger.error("Base folder path does not exist: %s", self.folder_path)
            return

        for folder in (d for d in self.folder_path.iterdir() if d.is_dir()):
            try:
                image_files = self.retrieve_image_files(folder)
                idle_images, speak_images = self.filter_and_validate_images(folder, image_files)
                self.save_processed_folder(folder, idle_images, speak_images, image_files)
            except (FileNotFoundError, ValueError) as e:
                self.logger.error("Error processing folder '%s': %s", folder.name, e)
                continue

    def retrieve_image_files(self, folder: Path) -> list:
        """
        <summary>Return all image files in the folder. Raises FileNotFoundError if none exist.</summary>
        <param name="folder">The model folder to scan.</param>
        <returns>List of image Path objects.</returns>
        """
        all_files = [f for f in folder.iterdir() if f.is_file()]
        image_files = [f for f in all_files if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif")]
        if not image_files:
            raise FileNotFoundError(f"No image files found in '{folder.name}'.")
        return image_files

    def filter_and_validate_images(self, folder: Path, image_files: list) -> tuple:
        """
        <summary>
        Separate images into idle and speak sets and validate that each set has at most one file.
        </summary>
        <param name="folder">The model folder (used in error messages).</param>
        <param name="image_files">All image files found in the folder.</param>
        <returns>A (idle_images, speak_images) tuple.</returns>
        """
        idle_images = [f for f in image_files if f.stem.lower().endswith("_idle")]
        speak_images = [f for f in image_files if f.stem.lower().endswith("_speak")]
        if len(idle_images) > 1:
            raise ValueError(f"Validation Error in '{folder.name}': only one '_idle' image is allowed.")
        if len(speak_images) > 1:
            raise ValueError(f"Validation Error in '{folder.name}': only one '_speak' image is allowed.")
        return idle_images, speak_images

    def save_processed_folder(
        self, folder: Path, idle_images: list, speak_images: list, image_files: list
    ) -> None:
        """
        <summary>Store the processed folder entry in processed_folders.</summary>
        <param name="folder">The model folder.</param>
        <param name="idle_images">List of idle image paths (0 or 1 items).</param>
        <param name="speak_images">List of speak image paths (0 or 1 items).</param>
        <param name="image_files">All image files in the folder.</param>
        """
        self.processed_folders[folder.name] = {
            "idle": idle_images[0] if idle_images else None,
            "speak": speak_images[0] if speak_images else None,
            "all_images": image_files,
        }
