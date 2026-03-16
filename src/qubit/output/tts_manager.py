"""
TTS Manager Module

This module provides functionality for managing Text-to-Speech (TTS) operations using the PiperVoice library.
It includes the TTSManager class which handles loading TTS models, configuring voices, and facilitating
speech synthesis for various applications.
"""
from piper import PiperVoice
from src.utils.log_utils import get_logger
from config.config import TTS_MODEL_NAME, ROOT



class TTSManager:
    """
    TTSManager

    A class for managing Text-to-Speech synthesis operations using PiperVoice.

    This class is responsible for loading TTS models, configuring voice settings, and providing
    an interface for synthesizing speech from text inputs. It handles model initialization,
    error logging, and maintains the voice instance for speech generation.

    Attributes:
        logger: Logger instance for logging operations.
        project_root: Path to the project root directory.
        model_path: Path to the TTS model file.
        voice: PiperVoice instance loaded from the model.
    """

    def __init__(self):
        """
        Initializes the TTSManager instance.

        Sets up the logger, determines the project root and model path, initializes the voice attribute,
        and loads the TTS model by calling _load_model().
        """
        self.logger = get_logger("TTSManager")

        self.project_root = ROOT
        self.model_path = self.project_root / TTS_MODEL_NAME
        self.voice = None

        self._load_model()
        

    def _load_model(self):
        """
        Loads the TTS model from the specified model path.

        Attempts to load the PiperVoice model using PiperVoice.load(). Logs success or failure.
        If loading fails, logs the error and re-raises the exception.

        Raises:
            Exception: If the model cannot be loaded (any exception from PiperVoice.load).
        """
        try:
            self.voice = PiperVoice.load(self.model_path)
            self.logger.info("[TTSManager] Loaded TTS model from %s", self.model_path)
        except Exception as e:
            self.logger.error("[TTSManager] Failed to load TTS model: %s", e)
            raise
