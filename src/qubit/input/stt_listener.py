"""
Speech-to-Text (STT) listener stub.

LAYER: Input (see ARCHITECTURE.md)

This module is a placeholder for future real-time speech-to-text integration.
It currently provides a no-op implementation so that the rest of the system
can be wired and tested without requiring audio libraries (pyaudio, whisper, etc.).

In the target architecture:
- A real implementation would capture microphone / audio file input
- Run inference (e.g. faster-whisper or similar)
- Publish InputEvent or TwitchChatEvent equivalents onto the event bus
- Be started as a Service or background task from bootstrap

It must remain free of heavy dependencies at import time (heavy mocking strategy in tests).

Current state (2026 refactor): pure stub to keep the input layer complete without
blocking non-audio environments.
"""

import asyncio


class SpeechToTextListener:
    """
    Placeholder for asynchronous speech-to-text input.

    Responsibilities (when implemented):
    - Capture live audio or process audio files
    - Transcribe to text
    - Publish events to the central event bus for downstream processing
      (CognitiveOrchestrator, MemoryWriter, etc.)

    Current implementation: no-op. Safe to instantiate and call in any environment.
    """

    async def listen(self, event_bus):
        """
        Start listening for speech input.

        Args:
            event_bus: The central EventBus to publish transcribed InputEvents to.

        Current behaviour: does nothing (stub).
        Future implementation will run an audio capture + transcription loop.
        """
        pass
