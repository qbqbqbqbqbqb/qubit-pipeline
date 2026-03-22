"""Model configuration registry.

This module defines available model configurations used by the application.
Each entry in MODEL_REGISTRY maps a model identifier to a ModelConfig
instance, which specifies loading parameters and text generation behaviour.

The configurations include model-specific settings such as quantisation,
prompt formatting, and sampling strategies via GenerationConfig.
"""

from src.qubit.models.model_config import ModelConfig, GenerationConfig

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
