"""Private model execution layer.

This module contains the actual model loading and inference implementations.
It is intentionally private (leading underscore) and should not be imported
outside the models package.

The goal is to keep LLMService as a pure orchestrator that does not know
about Hugging Face, torch, transformers, etc.
"""

from typing import Any
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

from src.qubit.models.model_config import ModelConfig, GenerationConfig


class _HuggingFaceExecutor:
    """
    Internal executor for a single Hugging Face model (private to the models package).

    Responsibilities (post-2026 SoC refactor):
    - Own all direct torch/transformers/peft usage so LLMService stays a pure orchestrator.
    - Handle model loading (quantization via BitsAndBytes, optional LoRA via PeftModel).
    - Perform actual text generation with correct token handling and generation kwargs.
    - Provide clean unload path for GPU memory release.

    This class is intentionally private (leading underscore). It is instantiated only by
    LLMService._get_executor() and must never be imported outside the models package.

    See llm_service.py for the public API and models/README.md for the architecture decision.
    """

    def __init__(self, config: ModelConfig) -> None:
        """
        Create executor and immediately load the model according to ModelConfig.

        Args:
            config: ModelConfig with name, quant flags, LoRA path, dtype, context length, etc.
        """
        self.config = config
        self._model: Any = None
        self._tokenizer: Any = None
        self._load()

    def _load(self) -> None:
        """Load tokenizer + model (with optional 4-bit quant + LoRA) and put model in eval mode."""
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=self.config.trust_remote_code
        )
        self._tokenizer.pad_token = self._tokenizer.eos_token

        quant_config = None
        if self.config.load_in_4bit:
            quant_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=self.config.torch_dtype
            )

        self._model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            quantization_config=quant_config,
            device_map="auto",
            torch_dtype=self.config.torch_dtype,
            trust_remote_code=self.config.trust_remote_code
        )

        if self._tokenizer.pad_token is not None and len(self._tokenizer) > self._model.config.vocab_size:
            self._model.resize_token_embeddings(len(self._tokenizer))

        if self.config.lora_path:
            self._model = PeftModel.from_pretrained(
                self._model,
                self.config.lora_path
            )

        self._model.eval()

    @property
    def tokenizer(self):
        """Expose the loaded tokenizer (used by LLMService for prompt formatting)."""
        return self._tokenizer

    def generate(
        self,
        formatted_prompt: str,
        max_new_tokens: int,
        effective_gen: GenerationConfig,
    ) -> str:
        """
        Run actual model.generate() and return the decoded continuation.

        This is the only public entry point called by LLMService.generate().

        Args:
            formatted_prompt: Already-assembled prompt string (role-mapped or chat-template).
            max_new_tokens: Hard cap for this generation.
            effective_gen: GenerationConfig merged from profile + runtime overrides.

        Returns:
            str: The generated text (stripped, special tokens removed).

        Raises:
            ValueError: If input token ids are out of tokenizer vocab range (safety check).
        """
        inputs = self._tokenizer(
            formatted_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_context_length
        ).to(self._model.device)

        vocab_size = len(self._tokenizer)

        if torch.any(inputs.input_ids >= vocab_size) or torch.any(inputs.input_ids < 0):
            raise ValueError(
                f"Input tokens out of range: vocab_size={vocab_size}, "
                f"max_input_id={inputs.input_ids.max()}, tokenizer_len={len(self._tokenizer)}"
            )

        gen_kwargs = self._build_generation_kwargs(max_new_tokens, effective_gen)

        outputs = self._model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs.get("attention_mask"),
            **gen_kwargs
        )

        return self._tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()

    def _build_generation_kwargs(self, max_new_tokens: int, gen: GenerationConfig) -> dict[str, Any]:
        """
        Assemble the exact kwargs dict passed to model.generate().

        Handles custom EOS tokens (including extra_eos_tokens from ModelConfig) and
        optional min_p. All sampling params come from the effective GenerationConfig.
        """
        eos_token_id = self._tokenizer.eos_token_id

        if self.config.extra_eos_tokens:
            eos_ids = [self._tokenizer.eos_token_id]
            vocab = self._tokenizer.get_vocab()

            for token in self.config.extra_eos_tokens:
                if token in vocab:
                    eos_ids.append(self._tokenizer.convert_tokens_to_ids(token))
                else:
                    try:
                        tid = self._tokenizer.convert_tokens_to_ids(token)
                        if tid is not None and tid >= 0:
                            eos_ids.append(tid)
                    except Exception:
                        pass

            eos_token_id = eos_ids

        kwargs = {
            "temperature": gen.temperature,
            "top_p": gen.top_p,
            "top_k": gen.top_k,
            "repetition_penalty": gen.repetition_penalty,
            "max_new_tokens": max_new_tokens,
            "do_sample": gen.do_sample,
            "pad_token_id": self._tokenizer.eos_token_id,
            "eos_token_id": eos_token_id,
        }

        if gen.min_p is not None:
            kwargs["min_p"] = gen.min_p

        return kwargs

    def unload(self) -> None:
        """
        Release model and tokenizer references and clear CUDA cache.

        Called by LLMService when switching profiles or during shutdown.
        """
        if self._model is not None:
            del self._model
        self._model = None
        self._tokenizer = None
        torch.cuda.empty_cache()
