# memory/

Persistent memory — stores significant moments from streams and surfaces them as context during generation.

## Files

| File | Responsibility |
|---|---|
| `service.py` | `MemoryService` — owns ChromaDB + SQLite stores, runs background reflection jobs, exposes recent history for RAG, injects memory into prompt assembly events |
| `memory_manager.py` | CRUD operations against ChromaDB and the SQLite index |
| `reflections_generator.py` | `ReflectionGenerator` — uses the `reflection` LLM profile to synthesise higher-level memories from raw entries |
| `writer.py` | `MemoryWriter` — `EventProcessor` that subscribes to `*_filtered` and `response_generated` events and routes writes to `MemoryService`; the only component that decides what gets stored |

## Storage

| Store | Contents |
|---|---|
| ChromaDB | Embedding-indexed memory entries for semantic retrieval |
| SQLite | Lightweight index of entry metadata (timestamps, types) |

Both stores live under the path configured in `env_config.settings`.

## Read / write flags

`FeatureFlags.memory_read` and `memory_write` gate retrieval and storage independently, toggled live from the frontend. When `memory_write` is off, `MemoryWriter` is a no-op. When `memory_read` is off, `MemoryService` skips the retrieval step during prompt assembly.

## Invariant

`MemoryWriter` is the only entry point for writes. No other component calls `MemoryService` write methods directly.
