# Models Layer

This package is responsible for all LLM interactions in Qubit.

It has been refactored (2026-05) into a clean, swappable system that makes it easy to:

- Use different models for different tasks (e.g. main chat vs memory reflections)
- Give each model its own prompt "ritual" (chat templates, role markers, system prompt style, etc.)
- Add or swap fine-tunes without touching cognitive, memory, or personality code

## Core Concepts

| Concept           | What it is                                                                 | Why it exists |
|-------------------|----------------------------------------------------------------------------|---------------|
| `LLMService`      | The main thing you call from the rest of the app                           | Central place to ask for generation by *logical role* ("main", "reflection", etc.) |
| `LLMProfile`      | A named bundle: `ModelConfig` + `PromptFormatter` + generation defaults    | One "flavour" of using an LLM (main personality, analytical reflections, monologue, etc.) |
| `PromptFormatter` | The piece that turns messages/text into the exact string a specific model likes | This is how we support wildly different fine-tunes without polluting the rest of the codebase |
| `ModelConfig`     | Loading settings (HF repo, 4-bit, LoRA path, etc.) + some legacy fields    | Still used under the hood for model loading |

## How to Generate Text (Recommended Way)

```python
from src.qubit.models.llm_service import LLMService
from src.qubit.models.model_registry import LLM_PROFILES

service = LLMService()
for profile in LLM_PROFILES.values():
    service.register_profile(profile)

# Main chat personality
response = await service.generate(
    profile="main",
    input="Hello! How are you today?",
    max_new_tokens=120
)

# Reflections / internal reasoning (can use completely different model + settings)
qa = await service.generate(
    profile="reflection",
    input=[{"role": "system", "content": "You are an analytical AI..."}, ...],
    max_new_tokens=300,
    overrides={"temperature": 0.2}
)
```

The service handles:
- Choosing the right model + prompt formatter for the profile
- Merging profile defaults with per-call overrides
- Async execution (runs blocking generation off the event loop)

## Current Default Profiles

- `"main"` — the personality that talks to chat / does live responses (currently Stheno with chat template)
- `"reflection"` — used by the memory system to generate Q&A memories (currently same model but with analytical framing + lower temperature)

Both can point at the **same underlying weights** without loading the model twice (deduplication is automatic).

## Adding or Switching a Model

1. Add the model to `MODEL_REGISTRY` in `model_registry.py` (or just reference it directly).
2. Create (or reuse) an `LLMProfile` in `LLM_PROFILES`:

```python
"my-cool-model": LLMProfile(
    key="my-cool-model",
    config=ModelConfig(
        model_name="username/my-finetune-7b",
        load_in_4bit=True,
        lora_path=...,
        system_model_specific_prompt="You are Qubit, a chaotic VTuber...",
    ),
    formatter=get_formatter("pygmalion"),   # or "chat_template", "reflection", "raw", etc.
    generation_defaults=GenerationConfig(temperature=0.95, ...),
),
```

3. Assign it to a logical role if you want:

```python
LLM_PROFILES["main"] = LLM_PROFILES["my-cool-model"]
# or
LLM_PROFILES["reflection"] = LLMProfile(...)  # completely different model
```

That's it. No other files need to change.

## Choosing a PromptFormatter

| Formatter          | Best for                              | Notes |
|--------------------|---------------------------------------|-------|
| `"chat_template"`  | Modern models with proper HF templates (Llama-3, Mistral, Qwen, etc.) | Preferred when available |
| `"pygmalion"` / `"role_mapped"` | Older Pygmalion-style, Mytho, etc. | Handles capitalised roles + system prompt prepending |
| `"reflection"`     | Internal reasoning tasks              | Adds analytical system instructions |
| `"raw"`            | Plain text, quick tests               | Safe default / migration fallback |

You can also write your own small formatter class and register it.

## Single-LLM vs Multi-LLM

**You do not have to run multiple models.**

- If you only define/use the `"main"` profile, the system behaves almost exactly like the old single-model setup.
- Even if you keep both `"main"` and `"reflection"` pointing at the same weights, the model is only loaded **once** thanks to automatic deduplication in `LLMService`.
- Want completely separate models later? Just change the `config=` for the `"reflection"` profile (or add a third profile). The memory system already supports it.

## Architecture Notes

The legacy single-model singleton approach (`ModelManager` / `AsyncHuggingFaceLLM`) has been fully removed.

Everything now flows through `LLMService` + named `LLMProfile`s. This is the canonical, forward-only design.

## Further Reading

- `ARCHITECTURE.md` — full design rationale, the three-layer model, migration plan, and future backend support.
- `model_registry.py` — where all profiles are actually defined.
- `prompt_formatters/` — the concrete implementations.

If you're just trying to make Qubit sound good with a new fine-tune, you almost certainly only need to touch `model_registry.py` and pick (or write) a formatter.
