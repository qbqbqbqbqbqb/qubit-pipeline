import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

from src.qubit.models.base_model_manager import BaseModelManager
from src.qubit.models.model_config import ModelConfig



class HuggingFaceModelManager(BaseModelManager):

    def __init__(self, config: ModelConfig):
        self.config = config
        self._load()

    def _load(self):
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

        if self.config.lora_path:
            self._model = PeftModel.from_pretrained(
                self._model,
                self.config.lora_path
            )

        self._model.eval()

    @property
    def model(self):
        return self._model

    @property
    def tokenizer(self):
        return self._tokenizer

    def _build_generation_config(self, max_new_tokens):
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

    def format_chat_prompt(self,messages):
        parts = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def generate_dialogue(self, prompt: str, max_new_tokens: int):

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

    def unload(self):
        del self._model
        torch.cuda.empty_cache()

    def prepare_prompt(self, prompt):
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