"""
Model registry and LLM profile initialization.

This module defines the available language model configurations,
selects the active model from application settings, and constructs
the LLM profiles used by the application.
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
    """
    Return the configured model, falling back to the default model if necessary.
    """
    active_key = settings.active_model

    if active_key not in MODEL_REGISTRY:
        print(
            f"[model_registry] WARNING: ACTIVE_MODEL='{active_key}' "
            "not found. Falling back to 'stheno'."
        )
        active_key = "stheno"

    return MODEL_REGISTRY[active_key]


def build_profile(
    key: str,
    model_config: ModelConfig,
    formatter_name: str,
) -> LLMProfile:
    """
    Create an LLM profile from a model configuration.
    """
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
    """
    Apply runtime generation setting overrides to a profile.
    """
    if temperature is not None:
        profile.generation_defaults.temperature = temperature

    if top_p is not None:
        profile.generation_defaults.top_p = top_p


base_config = get_active_model_config()

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
reflection_profile = build_profile(
    key="reflection",
    model_config=base_config,
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