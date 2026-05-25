# Generation Layer

This is the **single owner** of turning a high-level decision into an actual LLM call and `ResponseGeneratedEvent`.

## Responsibilities

- Own the queue of pending generation intents (`ResponsePromptEvent`)
- Assemble the final prompt (using `PromptAssembler` + all injections)
- Call the LLM via `LLMService`
- Publish the resulting `ResponseGeneratedEvent`

## Key Components

- `GenerationCoordinator` — the central `Service` with queue + `_run` loop
- Uses `PromptAssembler` + modules from `prompting/`
- Triggers memory RAG via `PromptAssemblyEvent`

## Design Rules

- Nothing outside this layer should directly call the LLM for chat/monologue responses.
- All prompt construction for generation intents funnels through here (or emits `ResponsePromptEvent` to it).
- The coordinator is intentionally a `Service` because it owns a queue and background processing.

## Flow

`response_prompt` event → `enqueue` → queue → `_generate_response` (assemble + LLM) → `_publish_response` → `ResponseGeneratedEvent`
