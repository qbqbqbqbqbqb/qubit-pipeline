# input/

Platform listeners. Gets external events onto the bus and nothing else — no filtering, no decisions.

| File | What it does |
|---|---|
| `audio_files.py` | Scans the audio directory for the frontend file list |
| `frontend_command_processor.py` | Translates WebSocket commands into lifecycle events and feature flag mutations. Subscribes to `bot_started` and `bot_end_stream` and normalises both into `frontend_command` events for the cognitive layer |
| `stt_listener.py` | Captures mic audio, transcribes via `faster-whisper`, publishes `stt_processed` |

## twitch/ · kick/

Each platform sub-package has the same shape:

| File | What it does |
|---|---|
| `auth.py` | Token acquisition and refresh. `kick_bot` and `kick_streamer` are token dicts, not client objects |
| `events.py` | Platform-specific raw event dataclasses |
| `listener.py` | Connects, subscribes, and publishes events onto the bus |
| `subscriptions.py` | Which channels and event types to listen for |

**twitch/** — EventSub + chat via `twitchAPI`. Publishes `twitch_chat`, `twitch_raid`, `twitch_follow`, `twitch_sub`, `twitch_gift`.

**kick/** — Pure HTTP + Pusher WebSocket. Publishes `kick_chat`. Auth stores token dicts only — no client `.close()` on teardown.

Input listeners publish raw events only. All filtering and decisions happen downstream.