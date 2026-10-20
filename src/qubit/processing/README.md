# processing/

Input processing layer. Sits between raw platform events and the cognitive layer. All processors are stateless `EventProcessor` subclasses — they receive events and publish new ones; they do not hold service state or make decisions.

## Files

| File | Responsibility |
|---|---|
| `common.py` | Shared utilities: `is_stale()` staleness check used by multiple processors |
| `moderation.py` | `ModerationProcessor` — first pass; filters banned words, sanitises usernames and text, emits `*_processed` events |
| `conversation.py` | `ConversationProcessor` — second pass; deduplicates via `MessageTracker`, drops stale messages, emits `*_filtered` events |
| `autonomous.py` | `AutonomousPromptProcessor` — handles monologue prompt events; applies staleness filtering before forwarding to generation |
| `chat_logger.py` | `ChatLogger` — appends filtered messages to `logs/chat_training.jsonl` when the `chat_logging` feature flag is on |

## Event flow

```
twitch_chat / kick_chat / stt_processed
        │
        ▼
 ModerationProcessor  ──►  *_processed
        │
        ▼
 ConversationProcessor  ──►  *_filtered
        │
        ├──►  CognitiveOrchestrator (via ActivityTracker)
        ├──►  MemoryWriter
        └──►  ChatLogger  (if chat_logging == True)
```

## Training log (`chat_logger.py`)

Output: `logs/chat_training.jsonl` — one JSON object per line.

```json
{"timestamp": "2026-10-20T14:00:00+00:00", "source": "twitch", "user": "someone", "text": "hello"}
```

Toggle via the **Chat Logging** button in the frontend control panel. Off by default. STT events are logged with `"user": "streamer"`.
