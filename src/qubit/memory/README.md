# Memory Layer

Split responsibility between writing and everything else.

## Components

| Component             | Type           | Responsibility |
|-----------------------|----------------|----------------|
| `MemoryWriter`        | `EventProcessor` | Pure writes to storage from events |
| `MemoryService`       | `Service`      | Owns Chroma + SQLite, public RAG getters, background reflection job |
| `MemoryManager`       | -              | Low-level collection management |
| `ReflectionsGenerator`| -              | Background Q&A reflection creation |

## Design Rules

- **Only `MemoryWriter`** may write to persistent storage from the event system.
- `MemoryService` provides read access for RAG (`get_recent_chat_history`, etc.).
- RAG injection happens via the `prompt_assembly` event (not direct calls from generation).
- Reflections run as a background job inside `MemoryService._run`.

## Current State (Post-Refactor)

- `MemoryHandler` (old router) has been removed from production.
- Clear separation between write path and read/RAG path.
