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
    """Internal executor for a single Hugging Face model.

    This class is responsible for:
    - Loading (with quant, LoRA, etc.)
    - Actual text generation
    - Resource cleanup

    It should only be used by LLMService.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._model: Any = None
        self._tokenizer: Any = None
        self._load()

    def _load(self) -> None:
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
        return self._tokenizer

    def generate(
        self,
        formatted_prompt: str,
        max_new_tokens: int,
        effective_gen: GenerationConfig,
    ) -> str:
        """Run generation with the given prompt and effective generation config."""
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
        """Unload model and free GPU memory."""
        if self._model is not None:
            del self._model
        self._model = None
        self._tokenizer = None
        torch.cuda.empty_cache()
