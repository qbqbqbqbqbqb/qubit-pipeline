"""Model configuration and LLM profile registry (fully config-driven).

MODEL_REGISTRY holds the catalog of available models.

LLM_PROFILES are built dynamically at import time using:
- ACTIVE_MODEL (which base model to use)
- MAIN_FORMATTER / REFLECTION_FORMATTER (optional formatter overrides)
- MAIN_TEMPERATURE / MAIN_TOP_P / REFLECTION_TEMPERATURE / REFLECTION_TOP_P (optional generation overrides)

Example .env:
    ACTIVE_MODEL=gpt6
    REFLECTION_FORMATTER=reflection
    REFLECTION_TEMPERATURE=0.25
"""

from src.qubit.models.model_config import ModelConfig, GenerationConfig
from src.qubit.models.llm_profile import LLMProfile
from src.qubit.models.prompt_formatters import get_formatter
from config.env_config import settings

# Registry mapping model identifiers to their configurations.
# Keys: str identifiers used to select a model.
# Values: ModelConfig instances defining loading and generation behaviour.
MODEL_REGISTRY = {

    "stheno": ModelConfig(
        model_name="Sao10K/L3-8B-Stheno-v3.2",
        load_in_4bit=True,
        trust_remote_code=False,
        use_chat_template=True,
        extra_eos_tokens=["<|eot_id|>", "<|end_of_text|>"],
        generation_config=GenerationConfig(
            temperature=1.14,
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.1,
            min_p=0.075
        )
    ),

    "gpt6": ModelConfig(
        model_name="PygmalionAI/pygmalion-6b",
        load_in_4bit=True,
        lora_path="training_data/training/qubit-lora-final",
        use_chat_template=False,
        system_model_specific_prompt="Respond as Qubit to this Twitch message.",
        default_prompt_formatter="pygmalion",   # important for config-driven loading
        generation_config=GenerationConfig(
            temperature=0.9,
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.1,
            do_sample=True
        )
    )
}


# ---------------------------------------------------------------------------
# LLM Profiles — fully driven by config (no hardcoding)
# ---------------------------------------------------------------------------

active_key = settings.active_model

if active_key not in MODEL_REGISTRY:
    print(f"[model_registry] WARNING: ACTIVE_MODEL='{active_key}' not found. Falling back to 'stheno'.")
    active_key = "stheno"

base_config = MODEL_REGISTRY[active_key]

# --- Formatters (already supported) ---
main_formatter = settings.main_formatter or base_config.default_prompt_formatter or "raw"
reflection_formatter = settings.reflection_formatter or "reflection"

# --- Build base profiles ---
main_profile = LLMProfile.from_model_config(
    key="main",
    model_config=base_config,
    formatter_name=main_formatter,
)

reflection_profile = LLMProfile.from_model_config(
    key="reflection",
    model_config=base_config,
    formatter_name=reflection_formatter,
)

# --- Apply per-profile generation overrides from config (if provided) ---
if settings.main_temperature is not None:
    main_profile.generation_defaults.temperature = settings.main_temperature
if settings.main_top_p is not None:
    main_profile.generation_defaults.top_p = settings.main_top_p

if settings.reflection_temperature is not None:
    reflection_profile.generation_defaults.temperature = settings.reflection_temperature
if settings.reflection_top_p is not None:
    reflection_profile.generation_defaults.top_p = settings.reflection_top_p

LLM_PROFILES: dict[str, LLMProfile] = {
    "main": main_profile,
    "reflection": reflection_profile,
}
