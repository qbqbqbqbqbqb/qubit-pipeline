import asyncio
import time
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig
)

from peft import PeftModel
from scripts2.managers.base_model_manager import BaseModelManager
from scripts2.utils.log_utils import get_logger


MODEL_NAME = "PygmalionAI/pygmalion-6b"
LORA_PATH = "training_data/training/qubit-lora-final" 


class ModelManager(BaseModelManager):

    __instance = None

    @property
    def _model(self):
        return self.__model

    @_model.setter
    def _model(self, value):
        self.__model = value

    @property
    def tokeniser(self):
        return self._tokeniser

    def __new__(cls):
        if cls.__instance is None:
            instance = super().__new__(cls)
            instance._init()
            cls.__instance = instance
        return cls.__instance

    def _init(self):
        self.logger = get_logger("PygmalionModelManager")

        try:
            self.logger.info("[ModelManager] Initializing Pygmalion + LoRA...")
            t0 = time.time()

            self._tokeniser = AutoTokenizer.from_pretrained(MODEL_NAME)
            self._tokeniser.pad_token = self._tokeniser.eos_token

            self.logger.info("[ModelManager] Tokeniser loaded.")

            self.logger.info("[ModelManager] Loading base model...")
            base_model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                device_map="auto",
                torch_dtype=torch.float16,
            )

            base_model.config.use_cache = True
            self.logger.info("[ModelManager] Attaching LoRA adapter...")
            self._model = PeftModel.from_pretrained(
                base_model,
                LORA_PATH
            )

            self._model.eval()

            self.logger.info(
                f"[ModelManager] Model ready in {time.time() - t0:.2f}s"
            )

        except Exception as e:
            self.logger.error(f"[ModelManager] Initialization failed: {e}", exc_info=True)
            raise

    def _get_generation_config(self, max_tokens: int):

        return {
            "temperature": 0.9,
            "top_p": 0.9,
            "top_k": 50,
            "repetition_penalty": 1.1,
            "do_sample": True,
            "max_new_tokens": max_tokens,
            "pad_token_id": self.tokeniser.eos_token_id,
            "eos_token_id": self.tokeniser.eos_token_id
        }

    def _format_prompt(self, message: str) -> str:
        return f"""Respond as Qubit to this Twitch message.
{message}
"""


    def generate_dialogue(
        self,
        prompt: str,
        max_tokens: int = 120,
        timeout: float = 60.0
    ) -> str:

        try:
            self.logger.debug("[Generation] Formatting prompt...")
            formatted_prompt = self._format_prompt(prompt)

            inputs = self._tokeniser(
                formatted_prompt,
                return_tensors="pt"
            ).to(self._model.device)

            gen_config = self._get_generation_config(max_tokens)

            self.logger.debug("[Generation] Running model.generate()")

            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    **gen_config
                )

            full_output = self._tokeniser.decode(
                outputs[0],
                skip_special_tokens=True
            )

            # Remove prompt from output
            response = full_output[len(formatted_prompt):].strip()

            return response

        except asyncio.TimeoutError:
            self.logger.warning("Generation timed out")
            return "Timed out"

        except Exception as e:
            self.logger.error(f"Generation failed: {e}", exc_info=True)
            return "Something went wrong!"

    @classmethod
    def get_instance(cls):
        return cls()