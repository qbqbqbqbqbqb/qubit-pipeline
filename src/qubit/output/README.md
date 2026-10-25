# output/

Receives `ResponseGeneratedEvent` and handles all output: voice, OBS, VTube Studio, PNG avatar, audio playback.

| File | What it does |
|---|---|
| `coordinator.py` | Owns the output queues, drives `ai_speaking` state, sanitises text, delegates to handlers. Passes `on_amplitude` callback to `TTSHandler.speak()` when VTube Studio is active |
| `tts_manager.py` | Loads and holds the Piper voice model. Model path built from `TTS_MODEL_NAME` in `config/settings.py` |

## handlers/

| File | Channel |
|---|---|
| `tts.py` | Streams Piper synthesis chunks into PyAudio. Measures per-chunk RMS amplitude and fires an `on_amplitude` callback before each chunk is written to the stream |
| `vtube.py` | VTube Studio WebSocket via pyvts. `inject_mouth(amplitude)` drives `JawOpen` and `MouthOpen` from real audio amplitude — VTS built-in mic lip sync should be disabled. Head movement, smile, blink, and eye gaze are still animation-loop driven |
| `obs.py` | OBS WebSocket — scene switching, source visibility, subtitle overlay (`TTS_SUBTITLE_NAME` from `config/settings.py`) |
| `png.py` | PNG avatar — frame switching for the browser source |
| `audio_player.py` | Manual audio file playback triggered from the frontend |
| `sanitiser.py` | Strips TTS-unfriendly characters and bot name prefix before synthesis. Bot name from `config/settings.py` |

## Queues

Two deques — priority (raids/gifts/follows, 120s staleness) and normal (everything else, 30s). Priority is always drained first. Both are capped so a stalled output can't grow unbounded. Stale items are dropped silently when popped.

## Mouth tracking

`TTSHandler` measures RMS amplitude per synthesis chunk and calls `VtubeStudioHandler.inject_mouth(amplitude)` immediately before writing each chunk to the audio stream. This drives `JawOpen` and `MouthOpen` from actual audio rather than a sine approximation. The virtual audio cable is no longer needed and VTS's built-in microphone lip sync should be turned off to avoid competing parameter writes.

Handlers don't import from `cognitive/`, `generation/`, or `processing/`.