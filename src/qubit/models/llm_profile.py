"""LLMProfile: binds a model config, formatter, and generation defaults into one logical unit."""

from dataclasses import dataclass, field, replace
from typing import Optional, Any

from src.qubit.models.model_config import ModelConfig, GenerationConfig
from src.qubit.models.prompt_formatters import get_formatter, PromptFormatter


@dataclass
class GenerationOverrides:
    """Per-call overrides for generation parameters."""
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None
    max_new_tokens: Optional[int] = None
    do_sample: Optional[bool] = None


@dataclass
class LLMProfile:
    """A complete, named configuration for one way of using an LLM.

    This is the primary unit the rest of the application selects by name
    ("main", "reflection", "monologue", etc.).

    Attributes:
        key: Stable identifier used to request this profile (e.g. "main", "reflection").
        config: The underlying ModelConfig (what HF model, quant, LoRA, etc.).
        formatter: The PromptFormatter instance that knows how to prepare prompts
            for this specific model/fine-tune.
        generation_defaults: Default sampling parameters for this profile.
    """

    key: str
    config: ModelConfig
    formatter: PromptFormatter = field(default_factory=lambda: get_formatter("raw"))
    generation_defaults: GenerationConfig = field(default_factory=GenerationConfig)

    @classmethod
    def from_model_config(
        cls,
        key: str,
        model_config: ModelConfig,
        formatter_name: str = "raw",
        generation_overrides: Optional[dict] = None,
    ) -> "LLMProfile":
        """Convenience constructor from an existing ModelConfig + formatter name.

        Does NOT mutate the original ModelConfig or its GenerationConfig (safe for shared registry objects).
        """
        fmt = get_formatter(formatter_name)

        # Start from a copy so we never mutate the source registry object
        gen_defaults = replace(model_config.generation_config)

        if generation_overrides:
            for k, v in generation_overrides.items():
                if hasattr(gen_defaults, k) and v is not None:
                    setattr(gen_defaults, k, v)

        return cls(
            key=key,
            config=model_config,   # we still reference the original config for loading (intentional)
            formatter=fmt,
            generation_defaults=gen_defaults,
        )
