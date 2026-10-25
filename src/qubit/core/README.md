# core/

Lifecycle and shared infrastructure. Everything imports from here; this package imports nothing from inside `qubit/`.

| File | What it does |
|---|---|
| `app.py` | Top-level container — holds `state`, `event_bus`, and the service list |
| `bootstrap.py` | Wires everything together. The only place construction order is defined |
| `event_bus.py` | Async pub/sub. Typed string event names, async dispatch |
| `event_processor.py` | Abstract base for stateless event handlers. Subclasses declare `SUBSCRIPTIONS` |
| `events.py` | Every typed `Event` dataclass in the application, including `StreamEndEvent` |
| `runtime.py` | Drives the asyncio lifecycle. Starts and stops services in order |
| `runtime_state.py` | `RuntimeState` + `FeatureFlags` — shared mutable state and feature toggles |
| `server.py` | WebSocket server on `ws://0.0.0.0:8765`. Bridges frontend to event bus |
| `service.py` | Abstract base for long-lived async services. Subclasses implement `start()` / `stop()` |

## FeatureFlags

All runtime toggles live here as typed booleans. Set via the `"toggle"` WebSocket action at any time — changes take effect on the next decision cycle.

| Flag | Default | What it controls |
|---|---|---|
| `twitch` | `True` | Twitch listener |
| `kick` | `True` | Kick listener |
| `stt` | `True` | Speech-to-text listener |
| `chat` | `True` | Chat response behaviour |
| `raids` | `True` | Raid reactions |
| `follow` | `True` | Follow reactions |
| `subs` | `True` | Sub reactions |
| `gifts` | `True` | Gift reactions |
| `monologue` | `True` | Idle monologue behaviour |
| `vtube_studio` | `True` | VTube Studio output |
| `png_output` | `False` | PNG avatar output |
| `memory_read` | `True` | Memory retrieval into prompts |
| `memory_write` | `True` | Writing events to memory |
| `chat_logging` | `False` | JSONL training log (`logs/chat_training.jsonl`) |
| `processing_active` | `True` | Input processing — set to `False` by end_stream |

## WebSocket actions (server.py)

| Action | What happens |
|---|---|
| `initialize` | Loads all LLM profiles via `ensure_loaded`. Models are not loaded at startup |
| `start` | Sets `start` lifecycle event, broadcasts initial feature states |
| `toggle` | Flips a `FeatureFlags` field by name at runtime |
| `end_stream` | Sets `processing_active=False`, publishes `bot_end_stream`, queues farewell monologue |
| `terminate` | Sets `shutdown` event — graceful process exit |
| `play_audio` | Plays a named audio file via `AudioFilePlayer` |
| `stop_audio` | Stops current audio playback |
| `list_audio_files` | Returns list of available audio files to frontend |
| `reconnect` | Forces WebSocket reconnect via `forceReconnect()` |

New feature toggles go in `FeatureFlags` only. Services never hold direct references to each other.