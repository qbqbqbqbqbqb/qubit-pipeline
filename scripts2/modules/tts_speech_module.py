import asyncio
import io
import itertools
import json
import wave

import numpy as np
import pyaudio
from scripts2.modules.base_module import BaseModule
from scripts2.managers.tts_manager import TTSManager
from piper import PiperVoice, SynthesisConfig
from scripts2.config.config import TTS_SPEAKER_NAME, TTS_DELAY
from scripts2.utils.tts_utils import normalise_text_for_tts
from scripts2.managers.obs_manager import OBSManager


class TtsSpeechModule(BaseModule):
    def __init__(self, signals, settings, tts_manager, tts_enabled = True):
        super().__init__("TTSSpeechModule")
        self.signals = signals
        self.settings = settings
        self.tts_enabled = tts_enabled
        self.tts_manager = tts_manager
        self.queue = asyncio.PriorityQueue()
        self.loop = None
        self.counter = itertools.count()
        self.obs_manager = OBSManager(self.settings)

    async def start(self):
        if not self.tts_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.loop = asyncio.get_running_loop()
        await super().start()

        self.signals.tts_module_ready.set()

    async def run(self):
        self.logger.info("[run] TTS module running...")

        while self._running:
            try:
                priority, count, event = await self.queue.get()
                self.logger.debug(f"[TTS] Dequeued item with priority {priority}: {event}")
                await self.consume_response(event)
                self.queue.task_done()

                await asyncio.sleep(TTS_DELAY)
            except Exception as e:
                self.logger.error(f"[run] Error while handling TTS queue item: {e}")

    def submit_response(self, event_data, priority=10):
            self.logger.debug(f"[TTS] submit_response called with priority {priority}: {event_data}")
            count = next(self.counter)
            asyncio.run_coroutine_threadsafe(
                self.queue.put((priority, count, event_data)), self._task.get_loop()
            )

    async def consume_response(self, event_data):
        try:
            event_type = event_data.get("type", "unknown")
            response_text = None

            if event_type == "response_generated":
                response_text = event_data.get("response")
            elif event_type == "chat_response_input":
                response_text = event_data.get("response")
            else:
                response_text = event_data.get("response")

            if not response_text:
                self.logger.warning(f"[consume_response] No text to speak for event type '{event_type}' in event_data: {event_data}")
                return

            self.logger.info(f"[TTS] Response: {response_text} (from: {event_type})")
            await self.speak(response_text)
        except Exception as e:
            self.logger.error(f"[consume_response] TTS error {e}")

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
            
            self.obs_manager.update_subtitle_text_and_style(
                new_text=text
            )

            normalised_text = normalise_text_for_tts(text)

            self.logger.info(f"[TTSModule] Speaking text: {normalised_text}")
            self.signals.ai_speaking.set()

            speaker_id = self._get_speaker_id()
            syn_config = self._build_synthesis_config(speaker_id)
            wav_bytes = self._generate_wav_bytes(normalised_text, syn_config)
            sample_rate, audio_np = self._decode_wav_bytes(wav_bytes)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._play_audio, sample_rate, audio_np)

        except Exception as e:
            self.logger.error(f"Error in TTS speak: {e}")
        finally:
            self.signals.ai_speaking.clear()

    def _get_speaker_id(self) -> int:
        json_path = self.tts_manager.model_path.with_suffix(".onnx.json")
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config["speaker_id_map"][TTS_SPEAKER_NAME]

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
                self.tts_manager.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
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

