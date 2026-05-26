# Input Layer

Contains listeners that produce raw external events.

## Current Sources

- `twitch/listener.py` — Twitch chat + events (via EventSub + IRC)
- `kick/listener.py` — Kick chat + events (pure HTTP + public Pusher WS, no extra library)
- `stt_listener.py` — real-time mic input via faster-whisper (feature-flagged "stt")
- Frontend command source

## Design

Listeners are `Service`s because they maintain long-lived connections.

They publish raw events (e.g. `twitch_chat_processed`) into the `EventBus`.

Raw events are then picked up by the **Processing** layer.
