"""Hugging Face model manager implementation.

This module provides HuggingFaceModelManager, a concrete implementation
of BaseModelManager for loading and interacting with Hugging Face
causal language models. It supports quantisation, LoRA adapters, and
customisable text generation settings.
"""

from typing import Any, Union, List, Dict, Optional
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

from src.qubit.models.base_model_manager import BaseModelManager
from src.qubit.models.model_config import ModelConfig

class HuggingFaceModelManager(BaseModelManager):
    """Model manager for Hugging Face causal language models.

    This class handles loading, configuring, and generating text from
    Hugging Face models. It supports optional quantisation (4-bit),
    LoRA adapters, and flexible prompt formatting.

    Attributes:
        config (ModelConfig): Configuration for model loading and generation.
    """

    def __init__(self: Any, config: ModelConfig) -> None:
        """Initialise the model manager and load the model.

        Args:
            config (ModelConfig): Model configuration settings.
        """
        self.config = config
        self._load()

    def _load(self: Any) -> None:
        """Load the tokenizer and model based on the configuration.

        This includes:
        - Initialising the tokenizer
        - Applying quantisation settings if enabled
        - Loading the model with device mapping
        - Attaching LoRA adapters if provided
        """
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name,
            trust_remote_code=self.config.trust_remote_code
        )
        self._tokenizer.pad_token = self._tokenizer.eos_token

        quant_config = Optional[BitsAndBytesConfig] = None
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

        if self.config.lora_path:
            self._model = PeftModel.from_pretrained(
                self._model,
                self.config.lora_path
            )

        self._model.eval()

    @property
    def model(self: Any) -> AutoModelForCausalLM:
        """Return the loaded Hugging Face model.

        Returns:
            Any: The underlying model instance.
        """
        return self._model

    @property
    def tokenizer(self: Any) -> AutoTokenizer:
        """Return the tokenizer associated with the model.

        Returns:
            Any: Tokenizer used for encoding and decoding text.
        """
        return self._tokenizer

    def _build_generation_config(self: Any, max_new_tokens: int) -> Dict[str, Any]:
        """Construct generation parameters for model inference.

        This method merges the configured GenerationConfig with runtime
        parameters such as max_new_tokens and resolves EOS token IDs.

        Args:
            max_new_tokens (int): Maximum number of tokens to generate.

        Returns:
            dict: Dictionary of generation parameters for model.generate().
        """
        gen = self.config.generation_config

        eos_token_id = self.tokenizer.eos_token_id

        if self.config.extra_eos_tokens:
            eos_ids = [self.tokenizer.eos_token_id]

            vocab = self.tokenizer.get_vocab()

            for token in self.config.extra_eos_tokens:
                if token in vocab:
                    eos_ids.append(self.tokenizer.convert_tokens_to_ids(token))

            eos_token_id = eos_ids

        config = {
            "temperature": gen.temperature,
            "top_p": gen.top_p,
            "top_k": gen.top_k,
            "repetition_penalty": gen.repetition_penalty,
            "max_new_tokens": max_new_tokens,
            "do_sample": gen.do_sample,
            "pad_token_id": self.tokenizer.eos_token_id,
            "eos_token_id": eos_token_id,
        }

        if gen.min_p is not None:
            config["min_p"] = gen.min_p

        return config

    def format_chat_prompt(self: Any, messages: List[Dict[str, str]]) -> str:
        """Format a list of chat messages into a plain text prompt.

        Args:
            messages (list[dict]): List of message dictionaries with
                'role' and 'content' keys.

        Returns:
            str: Formatted prompt string.
        """
        parts = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def generate_dialogue(self: Any, prompt: str, max_new_tokens: int) -> str:
        """Generate a response from the model.

        This method handles prompt formatting, tokenisation, and model
        inference, then decodes the generated tokens into text.

        Args:
            prompt (str | list): Input prompt or structured messages.
            max_new_tokens (int): Maximum number of tokens to generate.

        Returns:
            str: Generated response text.
        """
        if isinstance(prompt, list):
            prompt = self.format_chat_prompt(prompt)

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.config.max_context_length
        ).to(self.model.device)

        outputs = self.model.generate(
            **inputs,
            **self._build_generation_config(max_new_tokens)
        )

        return self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True
        ).strip()

    def unload(self: Any) -> None:
        """Unload the model and free GPU memory.

        This method deletes the model instance and clears CUDA cache
        to release GPU resources.
        """
        del self._model
        torch.cuda.empty_cache()

    def prepare_prompt(self: Any, prompt: Union[str, List[Dict[str, str]], Dict[str, str]]) -> str:
        """Prepare and normalise a prompt for model input.

        This method applies system prompts, chat templates, or fallback
        formatting depending on the input type and configuration.

        Args:
            prompt (str | list | dict): Input prompt in various formats.

        Returns:
            str: Prepared prompt string ready for tokenisation.
        """
        if self.config.system_model_specific_prompt and isinstance(prompt, str):
            prompt = f"{self.config.system_model_specific_prompt}\n{prompt}"

        if isinstance(prompt, list) and self.config.use_chat_template:
            return self.tokenizer.apply_chat_template(
                prompt,
                tokenize=False,
                add_generation_prompt=True
            )

        if isinstance(prompt, list):
            return "\n".join([m.get("content", "") for m in prompt])

        if isinstance(prompt, dict):
            return prompt.get("content", "")

        return str(prompt)
