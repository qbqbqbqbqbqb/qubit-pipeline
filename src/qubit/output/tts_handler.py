import asyncio
import io
import wave
import numpy as np
import pyaudio
from config.config import TTS_SPEAKER_NAME
from src.qubit.utils.tts_utils import normalise_text_for_tts
from src.qubit.output.tts_manager import TTSManager

class TTSHandler:
    """
    Async TTS module for speaking text with optional OBS subtitles.
    Can be used with OutputHandler's queue system.
    """

    def __init__(self, tts_manager=TTSManager()):
        """
        Args:
            tts_manager: Your TTSManager or Piper TTS engine instance
            vtube_module: Optional lip-sync module
        """
        self.tts_manager = tts_manager
        self._speaking_lock = asyncio.Lock()

    async def speak(self, text: str):
        """
        Speak the given text asynchronously.
        Handles VTube lip-sync if available.
        """
        if not text.strip():
            return

        normalised_text = normalise_text_for_tts(text)

        async with self._speaking_lock:
            wav_bytes = self._generate_wav_bytes(normalised_text)
            sample_rate, audio_np = self._decode_wav_bytes(wav_bytes)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._play_audio, sample_rate, audio_np)

    def _generate_wav_bytes(self, text: str) -> bytes:
        """
        Synthesize WAV bytes from text using TTS engine.
        """
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                speaker_id = self._get_speaker_id()
                syn_config = self._build_synthesis_config(speaker_id)
                self.tts_manager.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            return wav_io.getvalue()

    def _decode_wav_bytes(self, wav_data: bytes) -> tuple[int, np.ndarray]:
        """
        Decode WAV bytes into sample rate and numpy array for playback.
        """
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = wav_file.readframes(wav_file.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return sample_rate, audio_np

    def _play_audio(self, sample_rate: int, audio_np: np.ndarray):
        """
        Play the audio using PyAudio.
        """
        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            output=True,
            frames_per_buffer=1024
        )
        stream.write(audio_np.tobytes())
        stream.stop_stream()
        stream.close()
        pa.terminate()

    def _get_speaker_id(self) -> int:
        """
        Retrieve speaker ID from TTS manager's model config.
        """
        json_path = self.tts_manager.model_path.with_suffix(".onnx.json")
        import json
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config["speaker_id_map"][TTS_SPEAKER_NAME]

    def _build_synthesis_config(self, speaker_id: int):
        """
        Build the synthesis configuration for Piper.
        """
        from piper import SynthesisConfig
        return SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=0.9,
            noise_scale=0.3,
            noise_w_scale=0.5,
            volume=0.8,
            normalize_audio=True
        )