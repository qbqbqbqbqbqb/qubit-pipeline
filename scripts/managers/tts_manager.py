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
from scripts.utils.log_utils import get_logger

load_dotenv()

class TTSManager:
    """
    Handles text-to-speech synthesis, audio playback, and subtitle updates.
    """

    def __init__(self, signals):
        self.logger = get_logger("TTSModule")
        self.signals = signals

        this_file = Path(__file__).resolve()
        self.project_root = this_file.parent.parent.parent
        self.model_path = self.project_root / "en_GB-vctk-medium.onnx"

        self.voice = None
        self.inflect_engine = inflect.engine()
        self._load_model()

    def _load_model(self):
        try:
            self.voice = PiperVoice.load(self.model_path)
            self.logger.info(f"Loaded TTS model from {self.model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load TTS model: {e}")
            raise

    def _get_speaker_id(self) -> int:
        json_path = self.model_path.with_suffix(".onnx.json")
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config["speaker_id_map"][self.SPEAKER_NAME]

    def _build_synthesis_config(self, speaker_id: int) -> SynthesisConfig:
        return SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=0.9,
            noise_scale=0.3,
            noise_w_scale=0.5,
            volume=0.8,
            normalize_audio=True
        )

    def _generate_wav_bytes(self, text: str, syn_config: SynthesisConfig) -> bytes:
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                self.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            return wav_io.getvalue()

    def _decode_wav_bytes(self, wav_data: bytes) -> tuple[int, np.ndarray]:
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = wav_file.readframes(wav_file.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return sample_rate, audio_np

    def _play_audio(self, sample_rate: int, audio_np: np.ndarray):
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True,
            frames_per_buffer=1024,
        )
        stream.write(audio_np.tobytes())
        stream.stop_stream()
        stream.close()
        pa.terminate()

    async def speak(self, text: str):
        """
        Speak the given text with TTS, update subtitles, and play audio asynchronously.

        Args:
            text (str): The text to speak.
        """
        try:
            if not text.strip():
                self.logger.warning("Empty text received for TTS, skipping.")
                return

            self.logger.info(f"[TTSModule] Speaking text: {text}")
            if self.signals:
                self.signals.ai_speaking.emit(True)

            speaker_id = self._get_speaker_id()
            syn_config = self._build_synthesis_config(speaker_id)
            wav_bytes = self._generate_wav_bytes(text, syn_config)
            sample_rate, audio_np = self._decode_wav_bytes(wav_bytes)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._play_audio, sample_rate, audio_np)

            if self.signals:
                self.signals.ai_speaking.emit(False)

        except Exception as e:
            self.logger.error(f"Error in TTS speak: {e}")
            if self.signals:
                self.signals.ai_speaking.emit(False)
