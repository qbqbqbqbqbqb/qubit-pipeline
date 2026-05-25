

# qubit-pipeline

This is the main pipeline for Qubit.

> **Architecture note**: For the full layered model and responsibilities, see the `src/qubit/` subdirectories (each has its own README where relevant). The system follows a strict Separation of Concerns with these primary layers:

## Architecture Layers (Target SoC)

| Layer                | Responsibility                                      | Naming Convention          | Owns Loop? |
|----------------------|-----------------------------------------------------|----------------------------|------------|
| **Core / Runtime**   | Lifecycle, EventBus, shared state, wiring           | `core/`                    | Yes (runtime) |
| **Input Sources**    | Raw external events (Twitch, STT, etc.)             | `*Listener`                | Yes        |
| **Input Processing** | Filter, dedup, normalise, memory side-effects       | `*Processor`               | No         |
| **Cognitive**        | All "should I respond/monologue?" decisions         | `cognitive/` + `Orchestrator` | Ticker only |
| **Generation**       | Intent → full prompt → LLM → `ResponseGeneratedEvent` | `generation/` + `Coordinator` | Yes (queue) |
| **Memory**           | Write events + provide RAG + background reflections | `MemoryWriter` + `MemoryService` | Background only |
| **Output**           | Sanitise + coordinate TTS/OBS/VTube + speaking state | `OutputCoordinator`        | Yes (queue) |
| **Models**           | LLM loading, profiles, formatting                   | `models/`                  | No         |

### Core Principles
- `EventProcessor` = pure reactor (no `_run`)
- `Service` / `Coordinator` = owns loops, queues, or background work
- Cognitive layer is the **only** place that decides *what* to do
- Generation is the single path from intent to LLM response
- MemoryWriter is the only writer to persistent storage
- `RuntimeState` is the single source for cross-cutting flags (`ai_speaking`, features, etc.)

## Project Structure

```
src/qubit/
├── core/           # Runtime, EventBus, bootstrap, RuntimeState
├── input/          # Listeners (Twitch, STT, etc.)
├── processing/     # Pure processors (Conversation, Moderation, Autonomous)
├── cognitive/      # Decision making (Orchestrator, Tracker, Engine, Behaviours)
├── generation/     # Prompt assembly + LLM calls (Coordinator)
├── memory/         # Storage + RAG (Writer + Service + Manager)
├── output/         # Final delivery (Coordinator + handlers)
├── models/         # LLM profiles + formatters
└── prompting/      # Prompt modules & assembler (used by generation)
```

## Running

```bash
python -m pytest tests/qubit/ -q
```
---

**TODOs**:

- add speech to text
- add kick input
- add youtube input
- add audio file input
- add vtubestudio output
- add random events input -> on frontend start click
- figure out autonomous behaviour & decision-making system
- remove unnecessary old chat control utils

- update frontend to not be pure html eventually

- add ending stream input?
- update output logic to include emotes in text output but not tts output
