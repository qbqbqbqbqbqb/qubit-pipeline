"""Model configuration data structures.

This module defines dataclasses used to configure model loading and
text generation behaviour. It includes GenerationConfig for sampling
parameters and ModelConfig for model-level settings.
"""
from dataclasses import dataclass, field
from typing import Optional
import torch


@dataclass
class GenerationConfig:
    """Configuration for text generation sampling parameters.

    Attributes:
        temperature (float): Controls randomness in generation. Higher
            values increase diversity.
        top_p (float): Nucleus sampling probability threshold.
        top_k (int): Limits sampling to the top-k most likely tokens.
        repetition_penalty (float): Penalises repeated tokens to reduce
            redundancy.
        min_p (Optional[float]): Minimum probability threshold for token
            filtering, if supported.
        do_sample (bool): Whether to use sampling; if False, uses greedy decoding.
    """
    temperature: float = 0.9
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    min_p: Optional[float] = None
    do_sample: bool = True


@dataclass
class ModelConfig:
    """Configuration for model loading and runtime behaviour.

    Attributes:
        model_name (str): Hugging Face model identifier or local path.
        load_in_4bit (bool): Whether to load the model in 4-bit precision.
        load_in_8bit (bool): Whether to load the model in 8-bit precision.
        torch_dtype (torch.dtype): Torch data type for model weights.
        lora_path (Optional[str]): Path to LoRA adapter weights, if used.
        trust_remote_code (bool): Whether to allow execution of remote code.
        use_chat_template (bool): Whether to apply a chat template.
        chat_template_type (Optional[str]): Type of chat template to use.
        max_context_length (int): Maximum token context length supported.
        extra_eos_tokens (list[str] | None): Additional end-of-sequence tokens.
        system_model_specific_prompt (Optional[str]): System prompt tailored
            to the specific model.
        generation_config (GenerationConfig): Sampling configuration for
            text generation.
    """
    model_name: str
    load_in_4bit: bool = False
    load_in_8bit: bool = False
    torch_dtype: torch.dtype = torch.float16
    lora_path: Optional[str] = None
    trust_remote_code: bool = False
    use_chat_template: bool = False
    chat_template_type: Optional[str] = None
    max_context_length: int = 2048
    extra_eos_tokens: list[str] | None = None
    system_model_specific_prompt: Optional[str] = None
    generation_config: GenerationConfig = field(default_factory=GenerationConfig)
