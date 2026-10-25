# models/

LLM abstraction. Everything else calls `LLMService.generate(profile, ...)` and never touches a model directly.

| File | What it does |
|---|---|
| `llm_service.py` | Registers profiles, loads executors on demand via `ensure_loaded`, routes generation calls |
| `llm_profile.py` | Named profile — binds a model config to a formatter and generation defaults |
| `model_config.py` | Sampling parameters (temperature, top-p, max tokens, etc.) |
| `model_registry.py` | The list of profiles the application uses (`main`, `reflection`). `LLM_PROFILES` is iterated by `bootstrap.py` to register all profiles at startup |
| `_executor.py` | Low-level HuggingFace execution. Private to this package |

Models are not loaded at startup. `ensure_loaded` is called for each registered profile when the frontend sends the `initialize` WebSocket action. Calling `ensure_loaded` on an already-loaded profile is a no-op.

## prompt_formatters/

Converts a prompt string or message list into whatever token format a given model expects.

| File | What it does |
|---|---|
| `base.py` | Abstract base |
| `chat_template.py` | Uses the model's built-in `apply_chat_template` |
| `raw.py` | Passes the string through unchanged |
| `reflection.py` | Structured format for reflection-profile prompts |
| `role_mapped.py` | Remaps role names for models with non-standard conventions |
| `registry.py` | Maps formatter name strings to classes |

## Adding a profile

1. Add a `GenerationConfig` in `model_config.py` if you need different sampling settings
2. Add a `LLMProfile` in `model_registry.py` — it will be registered and loaded automatically on `initialize`