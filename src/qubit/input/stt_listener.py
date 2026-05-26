"""
Real-time Speech-to-Text (STT) listener using RealtimeSTT.

LAYER: Input (see ARCHITECTURE.md)

Uses KoljaB/RealtimeSTT (AudioToTextRecorder) for robust mic capture,
Silero VAD, and streaming transcription. This avoids raw PyAudio conflicts
with the TTS output path on Windows.

Supports optional input_device_index for multi-mic setups (set via
STT_INPUT_DEVICE_INDEX in .env).

Publishes SpeechEvent(type="stt_processed") directly (bypassing the public
chat moderation layer) since STT input comes from a trusted local source.

Heavy import is done inside the worker thread.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from src.qubit.core.service import Service
from src.qubit.core.events import SpeechEvent


class SpeechToTextListener(Service):
    """
    Microphone STT input source backed by RealtimeSTT.

    - Feature-flagged ("stt").
    - Publishes "stt_processed" events directly (no moderation step).
    - Clean shutdown via recorder.stop() + interrupt event.
    """

    def __init__(self, input_device_index: int | None = None):
        """
        Args:
            input_device_index: Optional PyAudio device index for the microphone.
                                Use utils or RealtimeSTT helpers to discover indices.
        """
        super().__init__("stt")
        self.input_device_index = input_device_index
        self._recorder = None
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self, app) -> None:
        await super().start(app)
        self._loop = asyncio.get_running_loop()

    async def _run(self: Any) -> None:
        await super()._run()
        while not self.app.state.shutdown.is_set():
            stt_enabled = self.app.state.features.get("stt", True)

            if not self.app.state.start.is_set() or not stt_enabled:
                await asyncio.sleep(0.5)
                continue

            if stt_enabled and self._worker_thread is None:
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._stt_worker, daemon=True, name="STT-RealtimeSTT"
                )
                self._worker_thread.start()
                self.logger.info("[_run] STT (RealtimeSTT) started")

            if not stt_enabled and self._worker_thread is not None:
                self._stop_worker()

            await asyncio.sleep(1)

    def _stop_worker(self):
        self._stop_event.set()
        if self._recorder is not None:
            try:
                self._recorder.stop()
                if hasattr(self._recorder, "interrupt_stop_event"):
                    self._recorder.interrupt_stop_event.set()
            except Exception:
                pass
        if self._worker_thread:
            self._worker_thread.join(timeout=4.0)
        self._worker_thread = None
        self._recorder = None
        self.logger.info("[_stop_worker] STT stopped")

    async def stop(self: Any) -> None:
        self._stop_worker()
        await super().stop()

    def _stt_worker(self):
        """Thread that owns the RealtimeSTT recorder."""
        try:
            from RealtimeSTT import AudioToTextRecorder
        except Exception as e:
            self.logger.error("RealtimeSTT not installed or failed to load: %s", e)
            return

        config = {
            "spinner": False,
            "language": "en",
            "use_microphone": True,
            "silero_sensitivity": 0.6,
            "silero_use_onnx": True,
            "post_speech_silence_duration": 0.4,
            "min_length_of_recording": 0,
            "min_gap_between_recordings": 0.2,
            "enable_realtime_transcription": True,
            "realtime_processing_pause": 0.2,
            "realtime_model_type": "tiny.en",
            "compute_type": "auto",
            "level": logging.ERROR,
        }
        if self.input_device_index is not None:
            config["input_device_index"] = self.input_device_index

        try:
            with AudioToTextRecorder(**config) as recorder:
                self._recorder = recorder
                self.logger.info("STT Ready (RealtimeSTT)")

                while not self._stop_event.is_set():
                    if not self._is_stt_enabled():
                        time.sleep(0.2)
                        continue
                    # Blocks until final transcription, then calls callback
                    recorder.text(self._on_final_text)
        except Exception as e:
            self.logger.error("RealtimeSTT worker error: %s", e)
        finally:
            self._recorder = None

    def _is_stt_enabled(self) -> bool:
        # Re-check inside the thread (best effort)
        try:
            return bool(self.app.state.features.get("stt", True))
        except Exception:
            return True

    def _on_final_text(self, text: str):
        text = (text or "").strip()
        if not text:
            return

        self.logger.info("[STT] Heard: %s", text)
        # Publish directly as processed — STT comes from a trusted local source
        # and does not go through the public chat moderation pipeline.
        event = SpeechEvent(
            type="stt_processed",
            text=text,
            data={"text": text, "source": "microphone"},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.event_bus.publish(event), self._loop
            )
