import re
import inflect
import pyaudio
import asyncio
import numpy as np
import wave
import io
import json
from pathlib import Path
import os
from dotenv import load_dotenv

from piper import PiperVoice, SynthesisConfig
from scripts2.utils.log_utils import get_logger
from scripts2.config.config import TTS_SPEAKER_NAME, TTS_MODEL_NAME


class TTSManager:
    """
    Handles model loading.
    """

    def __init__(self):
        self.logger = get_logger("TTSManager")

        this_file = Path(__file__).resolve()
        self.project_root = this_file.parent.parent.parent
        self.model_path = self.project_root / TTS_MODEL_NAME
        self.voice = None

        self._load_model()
        

    def _load_model(self):
        try:
            self.voice = PiperVoice.load(self.model_path)
            self.logger.info(f"Loaded TTS model from {self.model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load TTS model: {e}")
            raise


