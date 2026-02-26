from dataclasses import dataclass, field
from typing import Optional
import torch


@dataclass
class GenerationConfig:
    temperature: float = 0.9
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    min_p: Optional[float] = None
    do_sample: bool = True


@dataclass
class ModelConfig:
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