# Models Layer

This package is responsible for all LLM interactions in Qubit.

It is designed around a clean separation that makes it trivial to:
- Use completely different models (or the same model with different settings) for different tasks
- Give every model its own prompt "ritual" without polluting the rest of the codebase
- Add or swap fine-tunes with almost zero changes elsewhere

## Guiding Principle (Three Layers)

1. **Semantic / Content Layer** — *What* should the model think about or say?  
   (This is handled by `PromptAssembler`, personality modules, memory injections, reflection prompts, cognitive behaviours, etc.)

2. **Orchestration / Selection Layer** — *Which* model/profile should handle this task?  
   (`LLMService` + named profiles like `"main"`, `"reflection"`, `"monologue"`, etc.)

3. **Model-Specific Formatting + Execution Layer** — *How* do we turn the semantic payload into the exact text + generation parameters this particular fine-tune expects?  
   (This lives entirely inside `PromptFormatter` implementations.)

All the weird, model-specific incantations stay isolated in layer 3.

## Core Concepts

| Concept              | What it is                                                                 | Why it matters |
|----------------------|----------------------------------------------------------------------------|----------------|
| `LLMService`         | The central orchestrator you call from the rest of the app                 | Single entry point for all generation |
| `LLMProfile`         | A named unit: `ModelConfig` + `PromptFormatter` + generation defaults      | "main", "reflection", etc. — the logical roles |
| `PromptFormatter`    | Turns messages or assembled text into the exact string the model was trained on | The key to easy fine-tune swapping |
| `ModelConfig`        | Loading details (repo, quant, LoRA, etc.)                                  | What gets loaded |
| `GenerationOverrides`| Per-call sampling tweaks (temperature, max tokens, etc.)                   | Fine control without changing the profile |

## How Generation Works End-to-End

The high-level semantic layer (`PromptAssembler` + modules) produces either:
- A flat string (current main chat path via priority injections), or
- A list of `{"role": ..., "content": ...}` messages (reflections, future cognitive work)

This payload is passed to:

```python
await llm_service.generate(
    profile="main",           # or "reflection", etc.
    input=...,                # string or list of messages
    overrides=...
)
```

The chosen `LLMProfile`'s `PromptFormatter` then transforms it into the exact format the model expects before tokenization and generation.

This is why you can point `"main"` at a Llama-3 chat model (using `chat_template` formatter) and `"reflection"` at an older Pygmalion-style model (using `role_mapped` or `reflection` formatter) with no changes to the prompting or memory code.

## How to Generate Text

```python
from src.qubit.models.llm_service import LLMService
from src.qubit.models.model_registry import LLM_PROFILES

llm = LLMService()
for p in LLM_PROFILES.values():
    llm.register_profile(p)

# Normal chat response
reply = await llm.generate(profile="main", input=final_assembled_prompt, max_new_tokens=120)

# Reflection / internal reasoning (can be a completely different model)
qa = await llm.generate(
    profile="reflection",
    input=reflection_messages,
    overrides={"temperature": 0.25, "max_new_tokens": 400}
)
```

The service handles formatting, merging of defaults + overrides, and async execution.

## Current Default Profiles

- `"main"` — live personality responses (chat, monologues, etc.)
- `"reflection"` — analytical memory reflection generation

You can add as many more as you like (`"monologue"`, `"critique"`, `"planner"`, ...).

## Adding or Switching a Model

1. Define the model in `MODEL_REGISTRY` (in `model_registry.py`) if it doesn't exist.
2. Create an `LLMProfile` and add it to `LLM_PROFILES`:

```python
from src.qubit.models.llm_profile import LLMProfile
from src.qubit.models.model_config import ModelConfig, GenerationConfig
from src.qubit.models.prompt_formatters import get_formatter

LLM_PROFILES["my-new-finetune"] = LLMProfile(
    key="my-new-finetune",
    config=ModelConfig(
        model_name="username/my-cool-7b",
        load_in_4bit=True,
        lora_path=...,
    ),
    formatter=get_formatter("chat_template"),   # or "pygmalion", "reflection", "raw", custom...
    generation_defaults=GenerationConfig(temperature=0.92, top_p=0.95),
)
```

3. Use it:

```python
LLM_PROFILES["main"] = LLM_PROFILES["my-new-finetune"]   # switch main personality
# or
LLM_PROFILES["reflection"] = LLMProfile(...)             # different model for reflections
```

## Choosing a PromptFormatter

| Name                | Best for                                      | Notes |
|---------------------|-----------------------------------------------|-------|
| `chat_template`     | Modern HF models with proper chat templates   | Preferred when available (Llama-3, Mistral, etc.) |
| `pygmalion` / `role_mapped` | Older Pygmalion-style, MythoMax, etc.     | Handles capitalised roles + explicit system prompts |
| `reflection`        | Analytical / internal reasoning tasks         | Adds stricter system framing |
| `raw`               | Plain text or quick experiments               | Pass-through |

You can register custom formatters easily.

## Single-LLM vs Multi-LLM

You never have to run more than one model.

- Using only the `"main"` profile is perfectly valid.
- Even if `"main"` and `"reflection"` point at the same weights, `LLMService` automatically deduplicates and loads the model only once.
- Want a genuinely different (stronger, smaller, differently tuned) model for reflections? Just point the `"reflection"` profile at a different `ModelConfig`. The rest of the system doesn't care.

## Future Directions

- Support for additional backends (vLLM, llama.cpp, OpenAI-compatible APIs, etc.) behind the same `LLMService` interface.
- Dynamic profile loading / hot-swapping.
- Richer `GenerationRequest` objects (tool schemas, images, etc.).
- Per-profile observability and routing logic.

## Where to Look in the Code

- `model_registry.py` — current profile definitions
- `llm_service.py` — the orchestrator
- `llm_profile.py` — `LLMProfile` + `GenerationOverrides`
- `prompt_formatters/` — all the actual formatting logic
- `hf_model_manager.py` — the current concrete loader + generator (used by the service)

This is the complete, forward-only design. No legacy singletons remain.
