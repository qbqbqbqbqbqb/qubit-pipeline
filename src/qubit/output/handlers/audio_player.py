"""
Minimal audio file player for pre-converted RVC singing files.

Plays audio files with high priority so they are not interrupted
by chat, monologues, or TTS.
"""

import asyncio
import wave
from pathlib import Path

import pyaudio

from src.qubit.core.service import Service


class AudioFilePlayer(Service):
    """
    High-priority audio player for RVC pre-converted songs.

    Only responsibility: play a selected audio file without interruption.
    """

    def __init__(self, audio_directory: str | None = None):
        super().__init__("audio_file_player")
        self.audio_directory = Path(audio_directory) if audio_directory else Path("audio")
        self._playing = False
        self._current_file: str | None = None

    async def play_file(self, file_path: str) -> bool:
        if self._playing:
            self.logger.warning("[AudioFilePlayer] Already playing, ignoring request")
            return False

        full_path = self._resolve_path(file_path)
        if not full_path or not full_path.exists():
            self.logger.error("[AudioFilePlayer] File not found: %s", file_path)
            return False

        self._playing = True
        self._current_file = str(full_path)
        if self.app and hasattr(self.app, "state"):
            self.app.state.ai_speaking.set()

        self.logger.info("[AudioFilePlayer] Playing: %s", full_path.name)

        try:
            await asyncio.to_thread(self._play_wav_blocking, full_path)
        except Exception as e:
            self.logger.error("[AudioFilePlayer] Playback error: %s", e)
        finally:
            self._playing = False
            self._current_file = None
            if self.app and hasattr(self.app, "state"):
                self.app.state.ai_speaking.clear()
            self.logger.info("[AudioFilePlayer] Finished: %s", full_path.name)

        return True

    def _resolve_path(self, file_path: str) -> Path | None:
        p = Path(file_path)
        if p.is_absolute():
            return p
        return (self.audio_directory / p).resolve()

    def _play_wav_blocking(self, file_path: Path):
        wf = wave.open(str(file_path), 'rb')
        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pa.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )

        data = wf.readframes(1024)
        while data and self._playing:
            stream.write(data)
            data = wf.readframes(1024)

        stream.stop_stream()
        stream.close()
        pa.terminate()
        wf.close()

    def is_playing(self) -> bool:
        return self._playing

    async def stop_playback(self):
        if self._playing:
            self._playing = False
            if self.app and hasattr(self.app, "state"):
                self.app.state.ai_speaking.clear()
            self.logger.info("[AudioFilePlayer] Stop requested")
