# models/

LLM abstraction layer. Provides a single `LLMService` interface over multiple named model profiles. The rest of the application calls `LLMService.generate(profile, ...)` and never references a specific model directly.

## Files

| File | Responsibility |
|---|---|
| `llm_service.py` | `LLMService` — registers profiles, loads executors on demand, routes `generate()` calls, handles retries |
| `llm_profile.py` | `LLMProfile` — named profile binding a model config to a prompt formatter and generation defaults |
| `model_config.py` | `GenerationConfig` — sampling parameters (temperature, top-p, max tokens, etc.) |
| `model_registry.py` | `LLM_PROFILES` dict — the authoritative list of profiles used in the application (`main`, `reflection`, …) |
| `_executor.py` | `_HuggingFaceExecutor` — low-level HuggingFace `transformers` execution; internal to this package |

## `prompt_formatters/`

Each formatter converts a plain prompt string or message list into the token format a specific model expects.

| File | Formatter |
|---|---|
| `base.py` | Abstract base |
| `chat_template.py` | `ChatTemplateFormatter` — uses the model's built-in `apply_chat_template` |
| `raw.py` | `RawFormatter` — passes the string through unchanged |
| `reflection.py` | `ReflectionFormatter` — structured format for reflection-profile prompts |
| `role_mapped.py` | `RoleMappedFormatter` — remaps role names for models with non-standard conventions |
| `registry.py` | Maps formatter name strings to classes; used by `model_registry.py` |

## Adding a profile

1. Add a `GenerationConfig` entry in `model_config.py` if a new sampling config is needed.
2. Add a `LLMProfile` in `model_registry.py` with the model path, formatter, and config.
3. Call `llm_service.ensure_loaded("profile_name")` in `bootstrap.py`.
