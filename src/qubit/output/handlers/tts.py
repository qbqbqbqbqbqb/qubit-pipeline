"""
<summary>
TTSHandler — async wrapper for Piper TTS synthesis and PyAudio playback.
</summary>
<remarks>
Streams Piper synthesis chunks directly into a single PyAudio stream to avoid
per-chunk open/close overhead. Falls back to full WAV synthesis and playback
if the streaming generator raises.

A speaking lock serialises concurrent speak() calls so they queue naturally
rather than interleaving audio.
</remarks>
"""

import asyncio
import io
from typing import Any
import wave
import json
import numpy as np
from piper import SynthesisConfig
import pyaudio

from config.config import TTS_SPEAKER_NAME
from src.qubit.utils.tts_utils import normalise_text_for_tts
from src.qubit.output.tts_manager import TTSManager
from src.qubit.utils.log_utils import get_logger


class TTSHandler:
    """
    <summary>
    Async TTS handler that synthesises text via Piper and plays it through PyAudio.
    Used exclusively by OutputCoordinator.
    </summary>
    """

    def __init__(self: Any, tts_manager: TTSManager = None):
        """
        <summary>Initialise the handler with a TTSManager instance.</summary>
        <param name="tts_manager">The TTSManager holding the loaded Piper voice. Defaults to a new instance.</param>
        """
        self.tts_manager = tts_manager or TTSManager()
        self._speaking_lock = asyncio.Lock()
        self.logger = get_logger("TTSHandler")

    async def speak(self: Any, text: str) -> None:
        """
        <summary>
        Normalise the text, then synthesise and play it. Concurrent calls
        queue behind the speaking lock.
        </summary>
        <param name="text">The text to synthesise and speak.</param>
        """
        if not text.strip():
            return

        normalised_text = normalise_text_for_tts(text)

        if normalised_text != text:
            self.logger.info(
                "[TTSHandler] Normalised text (emojis/unsupported chars removed): %r -> %r",
                text, normalised_text,
            )

        async with self._speaking_lock:
            await self._speak_streaming(normalised_text)

    def _generate_wav_bytes(self: Any, text: str) -> bytes:
        """
        <summary>Synthesise full WAV bytes from text using the Piper voice. Used as fallback.</summary>
        <param name="text">Text to synthesise.</param>
        <returns>Complete WAV file contents as bytes.</returns>
        """
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                speaker_id = self._get_speaker_id()
                syn_config = self._build_synthesis_config(speaker_id)
                self.tts_manager.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            return wav_io.getvalue()

    def _decode_wav_bytes(self: Any, wav_data: bytes) -> tuple[int, np.ndarray]:
        """
        <summary>Decode WAV bytes into a (sample_rate, audio_array) pair for playback.</summary>
        <param name="wav_data">WAV file contents as bytes.</param>
        <returns>A (sample_rate, audio_np) tuple.</returns>
        """
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = wav_file.readframes(wav_file.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return sample_rate, audio_np

    def _play_audio(self: Any, sample_rate: int, audio_np: np.ndarray) -> None:
        """
        <summary>Play a numpy int16 audio array through PyAudio.</summary>
        <param name="sample_rate">Sample rate in Hz.</param>
        <param name="audio_np">Audio samples as a numpy int16 array.</param>
        """
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

    def _get_speaker_id(self: Any) -> int:
        """
        <summary>
        Read the speaker id from the Piper model's JSON config file.
        Falls back to 0 if the config cannot be read.
        </summary>
        <returns>The integer speaker id for the configured TTS_SPEAKER_NAME.</returns>
        """
        try:
            json_path = self.tts_manager.model_path.with_suffix(".onnx.json")
            with open(json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config["speaker_id_map"][TTS_SPEAKER_NAME]
        except Exception:
            return 0

    def _build_synthesis_config(self: Any, speaker_id: int) -> SynthesisConfig:
        """
        <summary>Build the Piper SynthesisConfig for the given speaker.</summary>
        <param name="speaker_id">The integer speaker id.</param>
        <returns>A configured SynthesisConfig instance.</returns>
        """
        return SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=0.9,
            noise_scale=0.3,
            noise_w_scale=0.5,
            volume=0.8,
            normalize_audio=True,
        )

    async def _speak_streaming(self: Any, text: str) -> None:
        """
        <summary>
        Stream Piper synthesis chunks into a single open PyAudio stream.
        Falls back to full WAV synthesis if the streaming generator raises.
        </summary>
        <param name="text">Normalised text to synthesise.</param>
        """
        speaker_id = self._get_speaker_id()
        syn_config = self._build_synthesis_config(speaker_id)

        loop = asyncio.get_running_loop()

        def _stream_synthesis_and_play():
            """Run in a thread: consume the Piper generator and feed one stream."""
            pa = pyaudio.PyAudio()
            stream = None
            try:
                for audio_chunk in self.tts_manager.voice.synthesize(
                    text, syn_config=syn_config
                ):
                    if stream is None:
                        sample_rate = 22050
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=sample_rate,
                            output=True,
                            frames_per_buffer=1024,
                        )

                    if isinstance(audio_chunk, (bytes, bytearray)):
                        stream.write(audio_chunk)
                    else:
                        stream.write(audio_chunk.tobytes())

            except Exception:
                wav_bytes = self._generate_wav_bytes(text)
                sr, full_audio = self._decode_wav_bytes(wav_bytes)
                if stream is None:
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=sr,
                        output=True,
                        frames_per_buffer=1024,
                    )
                stream.write(full_audio.tobytes())
            finally:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
                pa.terminate()

        await loop.run_in_executor(None, _stream_synthesis_and_play)
