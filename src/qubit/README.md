# src/qubit

Root package. Contains only `main.py` (entry point) and this README.
All application code lives in the sub-packages below.

## Package map

```
qubit/
├── core/           Application lifecycle, event bus, WebSocket server
├── cognitive/      Decision loop — what to do next
│   ├── activity/   Activity scoring and priority queues
│   ├── behaviours/ Pluggable decision strategies
│   └── decision/   Engine, arbiter, executor
├── input/          Platform listeners and input processing
│   ├── twitch/
│   ├── kick/
│   └── youtube/
├── processing/     Input filtering, deduplication, training log
├── generation/     Prompt assembly → LLM → ResponseGeneratedEvent
├── prompting/      Prompt assembler, injection modules
│   └── modules/
├── memory/         Persistent memory (ChromaDB + SQLite), reflections
├── models/         LLM profiles, executors, prompt formatters
│   └── prompt_formatters/
├── output/         TTS, OBS, VTube Studio, PNG model, audio player
│   └── handlers/
└── utils/          Shared utilities (logging, filtering, message tracking)
```

## Layered architecture

Data flows strictly top-to-bottom. No layer imports from a layer below it in this list.

```
Platform events (Twitch / Kick / STT)
        │
        ▼
 [ Input ]  ──── ModerationProcessor ──── ConversationProcessor ──── ChatLogger
        │
        ▼
 [ Cognitive ]  ── ActivityTracker ── DecisionEngine ── Behaviours
        │
        ▼
 [ Generation ]  ── PromptAssembler ── LLMService
        │
        ▼
 [ Output ]  ── TTSHandler ── OBSHandler ── VTubeStudioHandler
```

The `core/` event bus is the shared transport; every layer communicates through typed events, never direct method calls across boundaries.
