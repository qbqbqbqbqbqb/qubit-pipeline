"""
TTSHandler — async wrapper for Piper TTS synthesis and PyAudio playback.

Streams Piper synthesis chunks directly into a single PyAudio stream.
Per-chunk RMS amplitude is measured and forwarded to an optional on_amplitude
callback so VTube Studio can drive mouth movement from real audio rather than
a sine wave approximation.

Falls back to full WAV synthesis if the streaming generator raises.
A speaking lock serialises concurrent speak() calls so they queue naturally.
"""

import asyncio
import io
from typing import Any, Callable, Coroutine
import wave
import json
import numpy as np
from piper import SynthesisConfig
import pyaudio

from config.settings import TTS_SPEAKER_NAME
from src.qubit.utils.tts_utils import normalise_text_for_tts
from src.qubit.output.tts_manager import TTSManager
from src.qubit.utils.log_utils import get_logger

_INT16_MAX = 32768.0


class TTSHandler:

    def __init__(self: Any, tts_manager: TTSManager = None):
        self.tts_manager = tts_manager or TTSManager()
        self._speaking_lock = asyncio.Lock()
        self.logger = get_logger("TTSHandler")

    async def speak(
        self: Any,
        text: str,
        on_amplitude: Callable[[float], Coroutine] | None = None,
    ) -> None:
        """
        Normalise text, synthesise, and play. Concurrent calls queue behind the lock.

        on_amplitude — optional async callable invoked with a normalised RMS value
        (0.0–1.0) for each audio chunk before it is written to the stream. Used by
        VtubeStudioHandler.inject_mouth to drive mouth movement from real audio.
        """
        if not text.strip():
            return

        normalised_text = normalise_text_for_tts(text)

        if normalised_text != text:
            self.logger.info(
                "[speak] Normalised: %r -> %r", text, normalised_text,
            )

        async with self._speaking_lock:
            await self._speak_streaming(normalised_text, on_amplitude)

    def _generate_wav_bytes(self: Any, text: str) -> bytes:
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                speaker_id = self._get_speaker_id()
                syn_config = self._build_synthesis_config(speaker_id)
                self.tts_manager.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            return wav_io.getvalue()

    def _decode_wav_bytes(self: Any, wav_data: bytes) -> tuple[int, np.ndarray]:
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = wav_file.readframes(wav_file.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return sample_rate, audio_np

    def _get_speaker_id(self: Any) -> int:
        try:
            json_path = self.tts_manager.model_path.with_suffix(".onnx.json")
            with open(json_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config["speaker_id_map"][TTS_SPEAKER_NAME]
        except Exception:
            return 0

    def _build_synthesis_config(self: Any, speaker_id: int) -> SynthesisConfig:
        return SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=0.9,
            noise_scale=0.3,
            noise_w_scale=0.5,
            volume=0.8,
            normalize_audio=True,
        )

    @staticmethod
    def _rms_amplitude(chunk: bytes | bytearray | np.ndarray) -> float:
        """Return normalised RMS amplitude for an int16 audio chunk (0.0–1.0)."""
        if isinstance(chunk, (bytes, bytearray)):
            samples = np.frombuffer(chunk, dtype=np.int16)
        else:
            samples = np.asarray(chunk, dtype=np.int16)
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        return min(rms / _INT16_MAX, 1.0)

    async def _speak_streaming(
        self: Any,
        text: str,
        on_amplitude: Callable[[float], Coroutine] | None,
    ) -> None:
        speaker_id = self._get_speaker_id()
        syn_config = self._build_synthesis_config(speaker_id)
        loop = asyncio.get_running_loop()

        # Queue for amplitude values computed in the playback thread.
        # The thread puts values; the event loop task below calls on_amplitude.
        amp_queue: asyncio.Queue[float | None] = asyncio.Queue()

        async def _dispatch_amplitudes() -> None:
            """Drain the amplitude queue and fire on_amplitude callbacks."""
            while True:
                value = await amp_queue.get()
                if value is None:
                    break
                if on_amplitude is not None:
                    try:
                        await on_amplitude(value)
                    except Exception:
                        pass

        def _stream_synthesis_and_play() -> None:
            """Run in a thread: consume the Piper generator and feed one stream."""
            pa = pyaudio.PyAudio()
            stream = None
            try:
                for audio_chunk in self.tts_manager.voice.synthesize(text, syn_config=syn_config):
                    if stream is None:
                        stream = pa.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=22050,
                            output=True,
                            frames_per_buffer=1024,
                        )

                    amp = TTSHandler._rms_amplitude(audio_chunk)
                    loop.call_soon_threadsafe(amp_queue.put_nowait, amp)

                    if isinstance(audio_chunk, (bytes, bytearray)):
                        stream.write(audio_chunk)
                    else:
                        stream.write(audio_chunk.tobytes())

            except Exception:
                wav_bytes = self._generate_wav_bytes(text)
                sr, full_audio = self._decode_wav_bytes(wav_bytes)
                amp = TTSHandler._rms_amplitude(full_audio)
                loop.call_soon_threadsafe(amp_queue.put_nowait, amp)
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
                loop.call_soon_threadsafe(amp_queue.put_nowait, None)

        dispatch_task = asyncio.create_task(_dispatch_amplitudes())
        try:
            await loop.run_in_executor(None, _stream_synthesis_and_play)
        finally:
            await dispatch_task