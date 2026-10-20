# input/

Platform listeners and frontend command handling. Responsible for getting external events onto the bus — nothing more.

## Files

| File | Responsibility |
|---|---|
| `audio_files.py` | Utility for scanning the audio directory; used by the frontend list endpoint |
| `frontend_command_processor.py` | `FrontendCommandProcessor` — translates WebSocket commands from the control panel into lifecycle events and feature flag mutations |
| `stt_listener.py` | `SpeechToTextListener` — captures microphone audio, transcribes via `faster-whisper`, publishes `stt_processed` |

## Sub-packages

Each platform sub-package follows the same structure:

| File | Responsibility |
|---|---|
| `auth.py` | Token / credential acquisition and refresh |
| `events.py` | Platform-specific raw event dataclasses |
| `listener.py` | `*Listener` — `Service` that connects, subscribes, and publishes platform events onto the bus |
| `subscriptions.py` | Subscription helpers (which channels / event types to listen for) |

### `twitch/`
Connects to Twitch EventSub and chat via `twitchAPI`. Publishes `twitch_chat`, `twitch_raid`, `twitch_follow`, `twitch_sub`, `twitch_gift`.

### `kick/`
Connects to the Kick WebSocket API. Publishes `kick_chat`.

### `youtube/`
Placeholder — not yet implemented.

## Invariant

Input listeners publish raw events only. They do not filter, deduplicate, or make any decision about whether to respond. That work happens in `processing/` and `cognitive/`.
