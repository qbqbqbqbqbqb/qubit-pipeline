# generation/

Takes a `ResponsePromptEvent` and turns it into a `ResponseGeneratedEvent`. One file.

| File | What it does |
|---|---|
| `coordinator.py` | Owns the generation queue, assembles prompts via `PromptAssemblyEvent`, calls `LLMService`, publishes the result |

Drops stale requests before processing. Holds personality state (mood, tone, interaction level) that gets injected into every prompt — defaults come from `config/settings.py` and can be overridden at runtime from the frontend. Delegates prompt construction to `prompting/` and model execution to `models/`.

Models are not loaded at startup. `LLMService.ensure_loaded()` is called when the frontend sends the `initialize` action.

No knowledge of which platform a message came from or whether to respond — that's `cognitive/`'s job.