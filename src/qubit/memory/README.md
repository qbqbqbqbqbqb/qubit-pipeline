# memory/

Stores moments from streams and surfaces them as context during generation.

| File | What it does |
|---|---|
| `service.py` | Owns the ChromaDB + SQLite stores, runs reflection jobs, subscribes to `prompt_assembly` and appends memory injections to `contributions` |
| `memory_manager.py` | CRUD against ChromaDB and the SQLite index |
| `reflections_generator.py` | Uses the `reflection` LLM profile to synthesise higher-level memories from raw entries |
| `writer.py` | Subscribes to `*_filtered` and `response_generated`. The only entry point for writes |

## Storage

| Store | Contents |
|---|---|
| ChromaDB | Embedding-indexed entries for semantic retrieval |
| SQLite | Entry metadata (timestamps, types) |

Path configured in `env_config.settings`.

## Flags

`memory_read` and `memory_write` in `FeatureFlags` gate retrieval and storage independently, toggled live from the frontend.

When `memory_read` is off, `MemoryService` skips appending to `PromptAssemblyEvent.contributions` — nothing reaches the prompt.

When `memory_write` is off, `MemoryWriter.handle_event` is a no-op.

A reflection job runs when the number of unreflected entries reaches `REFLECTIONS_THRESHOLD` (set in `config/settings.py`).

`MemoryWriter` is the only component that calls `MemoryService` write methods directly.