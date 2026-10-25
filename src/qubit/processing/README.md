# processing/

Sits between raw platform events and the cognitive layer. All processors are stateless — they receive events, filter or transform them, and publish new ones.

| File | What it does |
|---|---|
| `common.py` | `is_stale()` — shared staleness check used by multiple processors |
| `moderation.py` | First pass. Filters banned words, sanitises text, emits `*_processed` |
| `conversation.py` | Second pass. Deduplicates via `MessageTracker`, drops stale messages (30s window checked on arrival), emits `*_filtered` |
| `autonomous.py` | Handles monologue prompt events. Staleness check before forwarding to generation |
| `chat_logger.py` | Appends filtered messages to `logs/chat_training.jsonl` when `chat_logging` is on |

```
twitch_chat / kick_chat / stt_processed
        │
        ▼
 ModerationProcessor  ──►  *_processed
        │
        ▼
 ConversationProcessor  ──►  *_filtered
        │
        ├──►  CognitiveOrchestrator
        ├──►  MemoryWriter
        └──►  ChatLogger  (if chat_logging == True)
```

## Staleness

Staleness is checked on event arrival in `ConversationProcessor`, not when the cognitive layer pulls from the queue. Messages that pass the 30s window are stored in `InputPriorityQueue` until consumed — they are never re-checked for age. This is intentional: a message that arrives fresh is always valid regardless of how long the decision loop was busy.

## Training log

`logs/chat_training.jsonl` — one JSON object per line. Off by default, toggled from the frontend control panel.

```json
{"timestamp": "...", "source": "twitch", "user": "someone", "text": "hello"}
```

STT events log with `"user": "streamer"`.