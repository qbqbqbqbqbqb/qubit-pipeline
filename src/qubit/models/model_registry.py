"""
Model registry and LLM profile initialization.

This module defines the available language model configurations,
selects the active model from application settings, and constructs
the LLM profiles used by the application.

Two profiles are always built:
  main       - used for chat responses and monologues
  reflection - used for memory reflection Q&A generation

If REFLECTION_MODEL is unset in .env (or matches ACTIVE_MODEL), both
profiles share the same underlying ModelConfig. LLMService.load_profile
detects this via _same_model_identity and reuses the already-loaded
executor — so no second model is loaded into VRAM.

If REFLECTION_MODEL names a different registry key, a genuinely separate
ModelConfig is used and LLMService loads it as a second executor.
"""

from config.env_config import settings
from src.qubit.models.llm_profile import LLMProfile
from src.qubit.models.model_config import GenerationConfig, ModelConfig


MODEL_REGISTRY: dict[str, ModelConfig] = {
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
            min_p=0.075,
        ),
    ),
    "gpt6": ModelConfig(
        model_name="PygmalionAI/pygmalion-6b",
        load_in_4bit=True,
        lora_path="training_data/training/qubit-lora-final",
        use_chat_template=False,
        system_model_specific_prompt="Respond as Qubit to this Twitch message.",
        default_prompt_formatter="pygmalion",
        generation_config=GenerationConfig(
            temperature=0.9,
            top_p=0.9,
            top_k=50,
            repetition_penalty=1.1,
            do_sample=True,
        ),
    ),
}


def get_active_model_config() -> ModelConfig:
    """Return the configured main model, falling back to 'stheno' if the key is invalid."""
    key = settings.active_model
    if key not in MODEL_REGISTRY:
        print(
            f"[model_registry] WARNING: ACTIVE_MODEL='{key}' not found in registry. "
            "Falling back to 'stheno'."
        )
        key = "stheno"
    return MODEL_REGISTRY[key]


def get_reflection_model_config() -> ModelConfig:
    """
    Return the ModelConfig for the reflection profile.

    If REFLECTION_MODEL is unset or resolves to the same registry key as
    ACTIVE_MODEL, the main ModelConfig is returned directly — LLMService
    will recognise the shared identity and reuse the loaded executor.
    """
    reflection_key = settings.reflection_model
    if not reflection_key:
        return get_active_model_config()

    if reflection_key not in MODEL_REGISTRY:
        print(
            f"[model_registry] WARNING: REFLECTION_MODEL='{reflection_key}' not found in registry. "
            "Falling back to active model."
        )
        return get_active_model_config()

    return MODEL_REGISTRY[reflection_key]


def build_profile(
    key: str,
    model_config: ModelConfig,
    formatter_name: str,
) -> LLMProfile:
    """Create an LLM profile from a model configuration."""
    return LLMProfile.from_model_config(
        key=key,
        model_config=model_config,
        formatter_name=formatter_name,
    )


def apply_generation_overrides(
    profile: LLMProfile,
    *,
    temperature: float | None,
    top_p: float | None,
) -> None:
    """Apply runtime generation setting overrides to a profile."""
    if temperature is not None:
        profile.generation_defaults.temperature = temperature

    if top_p is not None:
        profile.generation_defaults.top_p = top_p


base_config = get_active_model_config()
reflection_config = get_reflection_model_config()

# Profile used for general chat and conversation generation.
main_profile = build_profile(
    key="main",
    model_config=base_config,
    formatter_name=(
        settings.main_formatter
        or base_config.default_prompt_formatter
        or "raw"
    ),
)

apply_generation_overrides(
    main_profile,
    temperature=settings.main_temperature,
    top_p=settings.main_top_p,
)

# Profile used for reflection and self-analysis tasks.
# Uses reflection_config, which is either the same object as base_config
# (no second model loaded) or a distinct ModelConfig (separate executor).
reflection_profile = build_profile(
    key="reflection",
    model_config=reflection_config,
    formatter_name=settings.reflection_formatter or "reflection",
)

apply_generation_overrides(
    reflection_profile,
    temperature=settings.reflection_temperature,
    top_p=settings.reflection_top_p,
)

LLM_PROFILES: dict[str, LLMProfile] = {
    "main": main_profile,
    "reflection": reflection_profile,
}
