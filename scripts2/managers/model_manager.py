# === Setup sentence tokenisation ===
import asyncio
import time
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch

# === Setup colorlog logger ===
from scripts2.managers.base_model_manager import BaseModelManager
from scripts2.utils.log_utils import get_logger

"""
Module for managing the AI language model used in the application.

This module provides a singleton ModelManager class that handles the loading,
caching, and access to the Sao10K/L3-8B-Stheno-v3.2 language model with optimized
4-bit quantization. It ensures efficient memory usage and provides a centralized
way to access the model and tokenizer for text generation tasks.

Classes:
    ModelManager: Singleton manager for the AI model and tokenizer.
"""


MODEL_NAME = "Sao10K/L3-8B-Stheno-v3.2"

class ModelManager(BaseModelManager):
    """
    Singleton manager for the AI language model and tokeniser.

    Handles loading and caching of the Sao10K/L3-8B-Stheno-v3.2 model
    with 4-bit quantisation for memory efficiency. Uses singleton pattern
    to ensure only one instance exists across the application.

    Provides access to both the model and tokeniser for text generation tasks.
    """
    __instance = None

    @property
    def _model(self):
        """
        Get the loaded language model.

        Returns:
            AutoModelForCausalLM: The loaded language model instance.
        """
        return self.__model
    
    @property
    def __tokeniser(self):
        """
        Get the loaded tokenizer.

        Returns:
            PreTrainedTokenizer: The loaded tokenizer instance.
        """
        return self._tokeniser

    @property
    def _model(self, value):
        """
        Set the language model instance.

        Args:
            value (AutoModelForCausalLM): The language model instance to set.
        """
        self.__model = value

    @property
    def __new__(cls):

        """
        Create or return the singleton instance of ModelManager.

        This method implements the singleton pattern to ensure only one instance
        of the ModelManager exists throughout the application lifecycle.
        If an instance doesn't exist, it creates one and initializes it.
        If initialization fails, the exception is re-raised.

        Returns:
            ModelManager: The singleton instance of the ModelManager.
        """
        if cls.__instance is None:
            instance = super().__new__(cls)
            try:
                instance._init()
                cls.__instance = instance
            except Exception:
                raise
        return cls.__instance
    
    def _init(self):
        """
        Initialize the ModelManager instance.

        This method loads the tokenizer and the quantized language model from
        the pretrained Sao10K/L3-8B-Stheno-v3.2 model. It configures the tokenizer
        with appropriate padding settings and sets up 4-bit quantization for
        memory efficiency. The model is loaded with automatic device mapping.

        Raises:
            Exception: If model or tokenizer loading fails, re-raises the exception.
        """
        self.logger = get_logger("ModelManager")

        try:
            self.logger.info("[ModelManager] Initializing model...")
            t0 = time.time()

            # === Load tokenizer first ===
            self.logger.info("[ModelManager] Loading tokeniser...")
            self.__tokeniser = AutoTokenizer.from_pretrained(
                MODEL_NAME,
                trust_remote_code=False
            )
            self.__tokeniser.pad_token = self.__tokeniser.eos_token
            self.logger.info("[ModelManager] Tokeniser loaded.")

            # === Prepare quantisation config ===
            self.logger.info("[ModelManager] Preparing quantisation config...")
            quantisation_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16
            )

            # === Load model ===
            self.logger.info("[ModelManager] Loading model weights (this can take a few minutes)...")
            self._model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                quantization_config=quantisation_config,
                device_map="auto",
                trust_remote_code=False,
                dtype=torch.bfloat16,
            )
            self.logger.info(f"[ModelManager] Model loaded successfully in {time.time() - t0:.2f}s")

        except Exception as e:
            self.logger.error(f"[ModelManager] Model initialization failed: {e}", exc_info=True)
            raise
        

    def _get_generation_config(self, max_tokens: int):
        """
        Returns generation configuration parameters.
        """
        return {
            'temperature': 1.14,  
            'min_p': 0.075,
            'top_p': 0.9, 
            'top_k': 50,
            'max_new_tokens': max_tokens,
            'repetition_penalty': 1.1,
            'do_sample': True,
            'pad_token_id': self.tokeniser.eos_token_id,
            'eos_token_id': [
                self.tokeniser.eos_token_id,
                self.tokeniser.convert_tokens_to_ids("<|eot_id|>"),
                self.tokeniser.convert_tokens_to_ids("<|end_of_text|>")
            ] if "<|eot_id|>" in self.tokeniser.get_vocab() else self.tokeniser.eos_token_id
        }

    def generate_dialogue(self,
                            prompt: str,
                            max_new_tokens: int,
                            timeout: float = 60.0
                            ) -> str:
        """
        Performs the text generation call using transformers.
        """
        try:
            if isinstance(prompt, list): 
                prompt = self._apply_chat_template(prompt)

            self.logger.debug("[generate_text] Starting generation...")

            inputs = self.tokeniser(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self._model.device)

            loop = asyncio.get_running_loop()
            gen_config = self._get_generation_config(max_new_tokens)

            outputs = self._model.generate(
                        **inputs,
                        **gen_config
                    )

            generated_text = self.tokeniser.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()

            self.logger.debug("[generate_text] Generation completed...")
            self.logger.debug(f"[generate_text] Raw output: {generated_text[:60]}...")
            return generated_text

        except asyncio.TimeoutError:
            self.logger.warning(f"Text gen timed out after {timeout}")
            return "Timed out"
        except Exception as e:
            self.logger.warning(f"Failed generating text. {e}")
            return "Something went wrong!"

    def _apply_chat_template(self,
                            chat: list,
                            ) -> str:
        """
        Applies the chat template to the conversation for model input.

        Uses the tokenizer's apply_chat_template method to format the chat for generation.

        Args:
            chat (list): The chat conversation as a list of messages.

        Returns:
            str: The formatted chat string.

        Raises:
            Exception: If chat template application fails.
        """
        try:
            return self.tokeniser.apply_chat_template(
                chat,
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception as e:
            self.logger.error(f"Error applying chat template: {e}")
            raise
    
    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance of ModelManager.

        This class method provides a convenient way to access the singleton
        instance. It triggers the creation of the instance if it doesn't exist,
        or returns the existing one.

        Returns:
            ModelManager: The singleton instance of the ModelManager.
        """
        return cls()