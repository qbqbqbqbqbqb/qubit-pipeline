# qubit-pipeline

Python pipeline for running Qubit, an AI VTuber co-host. Receives live events from Twitch and Kick, decides whether and what to say using a scored-proposal cognitive layer, generates a response via a local LLM, and delivers it through TTS and OBS.

---

## Architecture

The pipeline is divided into strict layers. Each layer has a single defined responsibility and communicates exclusively through the `EventBus`. No layer calls another layer directly.

| Layer | Responsibility | Class convention | Owns loop? |
|---|---|---|---|
| **Core / Runtime** | Lifecycle, EventBus, `RuntimeState`, wiring | `core/` | Yes (runtime) |
| **Input** | Raw external events from Twitch, Kick, STT | `*Listener` | Yes |
| **Processing** | Filter, sanitise, deduplicate, normalise | `*Processor` | No |
| **Cognitive** | All response and monologue decisions | `cognitive/` + `Orchestrator` | Ticker only |
| **Generation** | Prompt assembly, LLM calls, retry | `GenerationCoordinator` | Yes (queue) |
| **Memory** | Persistence, RAG retrieval, background reflection | `MemoryWriter` + `MemoryService` | Background only |
| **Output** | TTS, OBS, VTube Studio, speaking state | `OutputCoordinator` | Yes (queue) |
| **Models** | LLM profiles, formatters, inference wrapper | `models/` | No |
| **Prompting** | Prompt modules and assembler | `prompting/` | No |

### Core principles

- `EventProcessor` is a pure reactor — no loops, no background work, no queues.
- `Service` / `Coordinator` owns loops, queues, or background tasks.
- The **Cognitive layer is the only place that decides** what to do and when. No other layer initiates a response.
- **Generation** is the single path from a decision to an LLM response. All calls to the LLM go through `GenerationCoordinator` → `LLMService`.
- **`MemoryWriter` is the only writer** to persistent storage.
- **`RuntimeState`** is the single source of truth for cross-cutting flags (`ai_speaking`, feature toggles, shutdown).
- All blocking I/O (SQLite, ChromaDB) runs off the event loop via `run_in_executor`.

---

## Event flow

```
Twitch / Kick / STT
        |
        v
   [*Listener]              raw events (twitch_chat, kick_chat, stt, ...)
        |
        v
[ModerationProcessor]       sanitise, filter banned words
        |                   publishes: twitch_chat_processed, kick_chat_processed, ...
        v
[ConversationProcessor]     deduplicate, staleness filter  (chat + STT only)
        |                   publishes: twitch_chat_filtered, kick_chat_filtered, stt_filtered
        v
[CognitiveOrchestrator]     scores behaviours every 5s tick, picks winner
        |                   publishes: response_prompt  or  monologue_prompt
        v
[GenerationCoordinator]     assembles prompt, calls LLM, retries up to MAX_GENERATION_ATTEMPTS
        |                   publishes: response_generated
        v
 [OutputCoordinator]        TTS, OBS subtitle, VTube Studio lip sync
        |
        v
  [MemoryWriter]            writes conversation items, monologues, responses to SQLite + ChromaDB
```

Community events (raids, follows, subscriptions) skip `ConversationProcessor` and go directly from `ModerationProcessor` to `CognitiveOrchestrator` and `MemoryWriter`.

---

## Cognitive decision system

`CognitiveOrchestrator` runs a 5-second ticker. On each tick it asks every registered `Behaviour` to score itself. The highest-scoring behaviour wins and its proposal is forwarded to `GenerationCoordinator`.

| Behaviour | Triggers |
|---|---|
| `ChatResponseBehaviour` | Unread chat or STT input in the queue |
| `IdleMonologueBehaviour` | Silence timeout exceeded |
| `FrontendTriggeredMonologueBehaviour` | Manual trigger from the frontend |
| `CommunityEventBehaviour` | Raid, follow, or subscription event |

STT input occupies a reserved high-priority slot in `InputPriorityQueue` and is never displaced by chat volume.

The prompt is assembled by `PromptAssembler` from composable injection modules. Static modules (`core_system_module`, `stream_type_module`) are built once at startup and reused. Dynamic modules (`personality_module`, `input_module`) are built fresh per request since they depend on runtime state or per-message input.

---

## Project structure

```
src/qubit/
├── core/           # Runtime, EventBus, bootstrap, RuntimeState
├── input/          # Listeners (Twitch, Kick, STT)
├── processing/     # ModerationProcessor, ConversationProcessor, AutonomousPromptProcessor
├── cognitive/      # CognitiveOrchestrator, ActivityTracker, DecisionEngine, Behaviours
├── generation/     # GenerationCoordinator, prompt assembly, LLM calls
├── memory/         # MemoryWriter, MemoryService, MemoryManager (SQLite + ChromaDB)
├── output/         # OutputCoordinator, TTS, OBS, VTube Studio handlers
├── models/         # LLM profiles, formatters, LLMService
└── prompting/      # PromptAssembler, injection modules
config/             # config.py — all tuneable constants
data/               # instructions.txt, blacklisted_words.txt, monologue_prompts.txt, ...
tests/              # pytest suite (asyncio_mode = auto)
```

---

## Configuration

All constants live in `config/config.py`. Key values:

| Constant | Default | Description |
|---|---|---|
| `MAX_GENERATION_ATTEMPTS` | `3` | LLM retry limit per request |
| `MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION` | `50` | Token budget for chat responses |
| `MAX_NEW_TOKENS_FOR_REFLECTION_GENERATION` | `200` | Token budget for memory reflections |
| `TTS_MODEL_NAME` | `en_GB-vctk-medium.onnx` | Piper TTS voice model |
| `TTS_SPEAKER_NAME` | `p236` | Speaker ID within the TTS model |
| `TTS_DELAY` | `1.5` | Seconds of silence injected after TTS playback |

Word lists and prompt data are loaded from `data/` at startup:

- `blacklisted_words.txt` — messages containing these are dropped at moderation
- `whitelisted_words.txt` — these override blacklist matches
- `monologue_prompts.txt` — pool of topics for idle monologue selection
- `instructions.txt` — core system personality prompt injected on every generation call

---

## Running

```bash
# Tests
python -m pytest tests/ -v

# Pipeline
python -X faulthandler -m src.qubit.main
```

---

## Dependencies (key)

| Package | Purpose |
|---|---|
| `twitchAPI` | Twitch EventSub and chat |
| `chromadb` | Vector store for RAG memory retrieval |
| `piper-tts` | Local neural TTS |
| `transformers` + `torch` | Local LLM inference |
| `spacy` | NLP utilities for input processing |
| `fastapi` + `uvicorn` | Frontend control server |
| `websockets` | Kick chat and VTube Studio connections |
| `pytest` + `pytest-asyncio` | Test suite |

Install: `pip install -r requirements.txt`
