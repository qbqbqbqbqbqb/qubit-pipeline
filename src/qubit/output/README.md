# output/

Delivery layer. Receives `ResponseGeneratedEvent` and drives all output channels: voice, OBS scene control, VTube Studio, PNG model, and audio playback.

## Files

| File | Responsibility |
|---|---|
| `coordinator.py` | `OutputCoordinator` — `Service` that owns the split output queue (priority + normal), manages `ai_speaking` state, delegates to all handlers |
| `tts_manager.py` | `TTSManager` — manages TTS engine lifecycle and audio rendering |

## `handlers/`

Each handler is a self-contained leaf responsible for one output channel.

| File | Handler | Channel |
|---|---|---|
| `tts.py` | `TTSHandler` | Text-to-speech audio synthesis and playback |
| `obs.py` | `OBSHandler` | OBS WebSocket — scene switching, source visibility |
| `vtube.py` | `VtubeStudioHandler` | VTube Studio WebSocket — model expression and motion |
| `png.py` | `PNGOutputHandler` | PNG model — frame switching for the browser-source avatar |
| `audio_player.py` | `AudioFilePlayer` | Manual audio file playback triggered from the frontend |
| `sanitiser.py` | `DialogueSanitiser` | Strips TTS-unfriendly characters and formatting before synthesis |

## Queue model

`OutputCoordinator` maintains two deques:

- **priority_queue** — community-event reactions (raids, gifts, follows). Drained first, longer staleness allowance.
- **queue** — everything else. Normal staleness cutoff.

Both queues are capped (`maxlen`) to prevent unbounded growth if output stalls.

## Invariant

No handler imports from `cognitive/`, `generation/`, or `processing/`. Handlers receive only what `OutputCoordinator` passes them and never inspect the originating event type to make decisions.
