# generation/

Prompt assembly and LLM execution. Converts a `ResponsePromptEvent` into a `ResponseGeneratedEvent`.

## Files

| File | Responsibility |
|---|---|
| `coordinator.py` | `GenerationCoordinator` — `Service` that owns the generation queue, assembles prompts via `PromptAssembler`, calls `LLMService`, and publishes the result |

## Responsibilities

- Maintains an async queue of pending `ResponsePromptEvent` items.
- Drops stale requests (older than `max_age_seconds`) before processing.
- Holds system personality state (mood, tone, interaction level) injected into every prompt.
- Delegates prompt construction to `prompting/`.
- Delegates model execution to `models/`.

## Invariant

This package has no knowledge of which platform a message came from, or whether Qubit should respond at all. Those decisions belong in `cognitive/`. `GenerationCoordinator` executes whatever it receives.
