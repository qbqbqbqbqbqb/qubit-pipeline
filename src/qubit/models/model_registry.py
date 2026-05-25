"""Model configuration and LLM profile registry.

MODEL_REGISTRY contains the raw ModelConfig definitions (loading + generation params).

LLM_PROFILES provides the higher-level named profiles used by LLMService.
Each profile combines a ModelConfig with a PromptFormatter and generation defaults.

This is the recommended way to define "main", "reflection", "monologue", etc.
"""

from dataclasses import replace

from src.qubit.models.model_config import ModelConfig, GenerationConfig
from src.qubit.models.llm_profile import LLMProfile
from src.qubit.models.prompt_formatters import get_formatter

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
# LLM Profiles (new multi-LLM architecture)
# These are the named units that LLMService and the rest of the app use.
# ---------------------------------------------------------------------------

LLM_PROFILES: dict[str, LLMProfile] = {
    "main": LLMProfile(
        key="main",
        config=MODEL_REGISTRY["stheno"],
        formatter=get_formatter("chat_template"),   # Stheno is Llama-3 based → good chat template
        generation_defaults=MODEL_REGISTRY["stheno"].generation_config,
    ),

    "reflection": LLMProfile(
        key="reflection",
        # We give it its own ModelConfig instance (same HF weights) so generation config is independent
        config=replace(
            MODEL_REGISTRY["stheno"],
            generation_config=GenerationConfig(
                temperature=0.3,
                top_p=0.9,
                top_k=50,
                repetition_penalty=1.05,
                do_sample=True,
            )
        ),
        formatter=get_formatter("reflection"),
        generation_defaults=replace(MODEL_REGISTRY["stheno"].generation_config, temperature=0.3, repetition_penalty=1.05),
    ),
}

# Convenience: the old "gpt6" entry can be turned into a profile on demand:
# LLM_PROFILES["gpt6-main"] = LLMProfile.from_model_config(
#     key="gpt6-main",
#     model_config=MODEL_REGISTRY["gpt6"],
#     formatter_name="pygmalion",
# )
