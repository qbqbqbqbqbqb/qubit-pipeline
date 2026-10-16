"""
<summary>
AudioFilePlayer — high-priority audio player for pre-converted RVC files.
</summary>
<remarks>
Plays a WAV file with priority over TTS by setting ai_speaking on RuntimeState
while playback is active. OutputCoordinator checks is_playing() and holds back
queued responses until the file finishes.
</remarks>
"""

import asyncio
import wave
from pathlib import Path

import pyaudio

from src.qubit.core.service import Service


class AudioFilePlayer(Service):
    """
    <summary>
    Service that plays WAV audio files with high priority.
    Only one file plays at a time; concurrent requests are rejected.
    </summary>
    """

    def __init__(self, audio_directory: str | None = None):
        """
        <summary>Initialise the player with an audio directory.</summary>
        <param name="audio_directory">Path to the directory containing audio files. Defaults to 'audio'.</param>
        """
        super().__init__("audio_file_player")
        self.audio_directory = Path(audio_directory) if audio_directory else Path("audio")
        self._playing = False
        self._current_file: str | None = None

    async def play_file(self, file_path: str) -> bool:
        """
        <summary>
        Play a WAV file by path. Rejects the request if playback is already active.
        Sets ai_speaking for the duration of playback.
        </summary>
        <param name="file_path">Relative or absolute path to the WAV file.</param>
        <returns>True if playback started and completed, False if rejected or the file was not found.</returns>
        """
        if self._playing:
            self.logger.warning("[AudioFilePlayer] Already playing, ignoring request")
            return False

        full_path = self._resolve_path(file_path)
        if not full_path or not full_path.exists():
            self.logger.error("[AudioFilePlayer] File not found: %s", file_path)
            return False

        self._playing = True
        self._current_file = str(full_path)
        if self.app and self.app.state:
            self.app.state.ai_speaking.set()

        self.logger.info("[AudioFilePlayer] Playing: %s", full_path.name)

        try:
            await asyncio.to_thread(self._play_wav_blocking, full_path)
        except Exception as e:
            self.logger.error("[AudioFilePlayer] Playback error: %s", e)
        finally:
            self._playing = False
            self._current_file = None
            if self.app and self.app.state:
                self.app.state.ai_speaking.clear()
            self.logger.info("[AudioFilePlayer] Finished: %s", full_path.name)

        return True

    def _resolve_path(self, file_path: str) -> Path | None:
        """
        <summary>
        Resolve a file path relative to audio_directory, or return it unchanged if absolute.
        </summary>
        <param name="file_path">The file path string to resolve.</param>
        <returns>A resolved Path, or None if the input is empty.</returns>
        """
        p = Path(file_path)
        if p.is_absolute():
            return p
        return (self.audio_directory / p).resolve()

    def _play_wav_blocking(self, file_path: Path) -> None:
        """
        <summary>
        Open and stream a WAV file using PyAudio in 1024-frame chunks.
        Stops early if _playing is cleared by stop_playback().
        </summary>
        <param name="file_path">Resolved path to the WAV file.</param>
        """
        wf = wave.open(str(file_path), "rb")
        pa = pyaudio.PyAudio()

        stream = pa.open(
            format=pa.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True,
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
        """<summary>Return True while a file is currently playing.</summary>"""
        return self._playing

    async def stop_playback(self) -> None:
        """
        <summary>
        Signal the current playback to stop at the next chunk boundary and clear ai_speaking.
        </summary>
        """
        if self._playing:
            self._playing = False
            if self.app and self.app.state:
                self.app.state.ai_speaking.clear()
            self.logger.info("[AudioFilePlayer] Stop requested")
