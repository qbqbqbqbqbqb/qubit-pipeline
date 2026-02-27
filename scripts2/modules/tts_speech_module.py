from collections import deque
import asyncio
import io
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
from scripts2.modules.vtube_studio_module import VTubeStudioModule
"""
This module provides Text-to-Speech (TTS) functionality for the application.

It integrates with Piper TTS engine, OBS for subtitles, and manages queues for speech synthesis.

Classes:
    TtsSpeechModule: Main class for handling TTS operations.
"""



class TtsSpeechModule(BaseModule):
    """
    A module for handling Text-to-Speech operations in the application.

    This class manages TTS synthesis, audio playback, subtitle updates via OBS,
    and handles queues for pairs and monologues.

    Attributes:
        signals: Signal object for event handling.
        settings: Application settings.
        tts_enabled: Boolean indicating if TTS is enabled.
        tts_manager: TTSManager instance.
        pairs_queue: Deque for storing pairs to speak.
        monologues_queue: Deque for storing monologues to speak.
        loop: Current event loop.
        obs_manager: OBSManager for subtitle updates.
    """
    def __init__(self, signals, settings, tts_manager, tts_enabled = True, vtube_module = None):
        """
        Initialize the TtsSpeechModule.

        Args:
            signals: Signal object for communication.
            settings: Application settings dictionary.
            tts_manager: TTSManager instance.
            tts_enabled (bool): Whether TTS is enabled. Defaults to True.
            vtube_module: Optional VTubeStudioModule instance for lip-sync.
        """
        super().__init__("TTSSpeechModule")
        self.signals = signals
        self.settings = settings
        self.tts_enabled = tts_enabled
        self.tts_manager = tts_manager
        self.vtube_module = vtube_module
        self.pairs_queue = deque()
        self.monologues_queue = deque()
        self.loop = None
        #self.obs_manager = OBSManager(self.settings)

    async def start(self):
        """
        Start the TTS module asynchronously.

        If TTS is disabled, logs a message and returns early.
        Sets up the event loop and signals readiness by setting tts_module_ready.
        """
        if not self.tts_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.loop = asyncio.get_running_loop()
        await super().start()

        self.signals.tts_module_ready.set()

    async def run(self):
        """
        Main loop for processing TTS queues.

        Processes pairs and monologues alternately, speaking them with delays.
        Handles exceptions during processing and logs errors.
        Runs continuously while _running is True.
        """
        self.logger.info("[run] TTS module running...")

        while self._running:
            try:
                if self.pairs_queue:
                    pair = self.pairs_queue.popleft()
                    self.logger.debug(f"[TTS] Processing pair: {pair}")
                    await self.speak(pair['user_text'])
                    await self.speak(pair['response_text'])

                    for _ in range(1):
                        if self.monologues_queue:
                            monologue = self.monologues_queue.popleft()
                            self.logger.debug(f"[TTS] Processing monologue after pair: {monologue}")
                            await self.speak(monologue['text'])
                        else:
                            break
                else:
                    if self.monologues_queue:
                        monologue = self.monologues_queue.popleft()
                        self.logger.debug(f"[TTS] Processing monologue: {monologue}")
                        await self.speak(monologue['text'])

                await asyncio.sleep(TTS_DELAY)
            except Exception as e:
                self.logger.error(f"[run] Error while handling TTS queue item: {e}")

    def submit_pair(self, pair):
        """
        Submit a pair to the TTS queue for speaking.

        Args:
            pair (dict): Dictionary containing 'user_text' and 'response_text' keys.
        """
        self.logger.debug(f"[TTS] submit_pair called: {pair}")
        self.pairs_queue.append(pair)

    def submit_monologue(self, monologue):
        """
        Submit a monologue to the TTS queue for speaking.

        Args:
            monologue (dict): Dictionary containing 'text' key.
        """
        self.logger.debug(f"[TTS] submit_monologue called: {monologue}")
        self.monologues_queue.append(monologue)

    async def speak(self, text: str):
        """
        Asynchronously speak the given text using TTS.

        Normalizes the text for TTS, updates OBS subtitles, synthesizes speech using Piper,
        decodes the WAV data, and plays the audio. Sets and clears the ai_speaking signal.

        Args:
            text (str): The text to be spoken.

        Raises:
            Exception: If any error occurs during text normalization, synthesis, or playback.
        """
        try:
            if not text.strip():
                self.logger.warning("Empty text received for TTS, skipping.")
                return
            
            """             self.obs_manager.update_subtitle_text_and_style(
                new_text=text
            ) """

            normalised_text = normalise_text_for_tts(text)

            self.logger.info(f"[TTSModule] Speaking text: {normalised_text}")
            self.signals.ai_speaking.set()

            speaker_id = self._get_speaker_id()
            syn_config = self._build_synthesis_config(speaker_id)
            wav_bytes = self._generate_wav_bytes(normalised_text, syn_config)
            sample_rate, audio_np = self._decode_wav_bytes(wav_bytes)

            mouth_task = None
            if self.vtube_module:
                    self.logger.info("Starting VTube Studio lip-sync animation")
                    self.vtube_module.speaking = True
                    mouth_task = asyncio.create_task(self.vtube_module.mouthanimation())
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._play_audio, sample_rate, audio_np)

            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._play_audio, sample_rate, audio_np)

        except Exception as e:
            self.logger.error(f"Error in TTS speak: {e}")
        finally:
            self.signals.ai_speaking.clear()
            if self.vtube_module:
                self.vtube_module.speaking = False
                if mouth_task:
                    await mouth_task

    def _get_speaker_id(self) -> int:
        """
        Retrieve the speaker ID from the TTS model configuration file.

        Loads the JSON config file associated with the TTS model and extracts
        the speaker ID for the configured speaker name.

        Returns:
            int: The speaker ID.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            KeyError: If TTS_SPEAKER_NAME is not found in speaker_id_map.
            json.JSONDecodeError: If the JSON file is invalid.
        """
        json_path = self.tts_manager.model_path.with_suffix(".onnx.json")
        with open(json_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config["speaker_id_map"][TTS_SPEAKER_NAME]

    def _build_synthesis_config(self, speaker_id: int) -> SynthesisConfig:
        """
        Build the synthesis configuration for Piper TTS.

        Args:
            speaker_id (int): The speaker ID to use for synthesis.

        Returns:
            SynthesisConfig: The configured synthesis settings with predefined parameters.
        """
        return SynthesisConfig(
            speaker_id=speaker_id,
            length_scale=0.9,
            noise_scale=0.3,
            noise_w_scale=0.5,
            volume=0.8,
            normalize_audio=True
        )

    def _generate_wav_bytes(self, text: str, syn_config: SynthesisConfig) -> bytes:
        """
        Generate WAV audio bytes from text using Piper TTS synthesis.

        Args:
            text (str): The text to synthesize into speech.
            syn_config (SynthesisConfig): The synthesis configuration.

        Returns:
            bytes: The WAV audio data as bytes.
        """
        with io.BytesIO() as wav_io:
            with wave.open(wav_io, "wb") as wav_file:
                self.tts_manager.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            return wav_io.getvalue()

    def _decode_wav_bytes(self, wav_data: bytes) -> tuple[int, np.ndarray]:
        """
        Decode WAV bytes into sample rate and numpy array for audio playback.

        Args:
            wav_data (bytes): The WAV audio data.

        Returns:
            tuple[int, np.ndarray]: A tuple containing the sample rate (int) and
            audio data as a numpy array (np.ndarray) of int16 values.
        """
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                audio_data = wav_file.readframes(wav_file.getnframes())
                audio_np = np.frombuffer(audio_data, dtype=np.int16)
        return sample_rate, audio_np

    def _play_audio(self, sample_rate: int, audio_np: np.ndarray):
        """
        Play the audio data using PyAudio.

        Initializes PyAudio, opens an output stream, writes the audio data,
        and terminates the PyAudio instance.

        Args:
            sample_rate (int): The audio sample rate in Hz.
            audio_np (np.ndarray): The audio data as a numpy array of int16 values.
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

    async def stop(self):
        """
        Stop the TTS module asynchronously.

        Calls the superclass stop method to perform cleanup.
        """
        await super().stop()

