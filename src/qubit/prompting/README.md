# prompting/

Assembles the final prompt from ordered injection modules.

| File | What it does |
|---|---|
| `injections.py` | `PromptInjection` dataclass and priority constants |
| `prompt_assembler.py` | Collects injections, sorts by priority, concatenates into the final prompt |

## modules/

Each module is a function returning a `PromptInjection`. `GenerationCoordinator` calls the relevant modules when handling a `PromptAssemblyEvent` — subscribers (e.g. `MemoryService`) can append their own injections to `contributions` before the assembler runs.

| File | Injects |
|---|---|
| `core.py` | System prompt loaded from `src/data/system_prompt.txt` |
| `personality.py` | Current mood, tone, interaction level from `GenerationCoordinator` |
| `stream_type.py` | Current stream type from `config/settings.py` |
| `input.py` | The triggering message or STT transcript |
| `chat.py` | Recent chat history |
| `reflection.py` | Relevant memories retrieved from `MemoryService` (when `memory_read` is on) |

To add a module: create `modules/my_module.py` returning a `PromptInjection` with an appropriate priority, then call it in `GenerationCoordinator` when building the assembler.