# prompting/

Prompt construction. Assembles the final prompt string from ordered injection modules before handing it to `LLMService`.

## Files

| File | Responsibility |
|---|---|
| `injections.py` | `PromptInjection` dataclass and priority constants (e.g. `USER_INPUT_PRIORITY`) |
| `prompt_assembler.py` | `PromptAssembler` — collects injections, sorts by priority, concatenates into a final prompt |

## `modules/`

Each module is a function that returns a `PromptInjection` for a specific concern.

| File | Injection content |
|---|---|
| `core.py` | Base system prompt — Qubit's identity, role, hard rules |
| `personality.py` | Current mood, tone, and interaction level from `GenerationCoordinator` |
| `stream_type.py` | Context about the current stream type or game |
| `input.py` | The triggering user message or STT transcript |
| `chat.py` | Recent chat history for context |
| `reflection.py` | Relevant memories retrieved from `MemoryService` |

## Adding a module

1. Create `modules/my_module.py` returning a `PromptInjection` with an appropriate priority constant.
2. Import and call it in `GenerationCoordinator` when building the `PromptAssembler` for the relevant request type.
