"""
<summary>
TTSManager — loads and owns the PiperVoice TTS model.
</summary>
<remarks>
Responsible for loading the TTS model at startup, logging success or failure,
and maintaining the voice instance used by TTSHandler for synthesis.
</remarks>
"""

from piper import PiperVoice
from src.qubit.utils.log_utils import get_logger
from config.config import TTS_MODEL_NAME, ROOT


class TTSManager:
    """
    <summary>
    Loads and holds a PiperVoice model instance for Text-to-Speech synthesis.
    Raises on construction if the model cannot be loaded.
    </summary>
    """

    def __init__(self):
        """
        <summary>
        Initialise the manager, derive the model path from config, and load the voice.
        </summary>
        """
        self.logger = get_logger("TTSManager")
        self.project_root = ROOT
        self.model_path = self.project_root / TTS_MODEL_NAME
        self.voice = None
        self._load_model()

    def _load_model(self) -> None:
        """
        <summary>
        Load the PiperVoice model from the configured path.
        Logs an error and re-raises on failure.
        </summary>
        """
        try:
            self.voice = PiperVoice.load(self.model_path)
            self.logger.info("[TTSManager] Loaded TTS model from %s", self.model_path)
        except Exception as e:
            self.logger.error("[TTSManager] Failed to load TTS model: %s", e)
            raise
