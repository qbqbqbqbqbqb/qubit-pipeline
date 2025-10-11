# === Setup sentence tokenisation ===
import time
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch

# === Setup colorlog logger ===
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

class ModelManager:
    """
    Singleton manager for the AI language model and tokeniser.

    Handles loading and caching of the Sao10K/L3-8B-Stheno-v3.2 model
    with 4-bit quantisation for memory efficiency. Uses singleton pattern
    to ensure only one instance exists across the application.

    Provides access to both the model and tokeniser for text generation tasks.
    """
    __instance = None
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
            self.tokeniser = AutoTokenizer.from_pretrained(
                MODEL_NAME,
                trust_remote_code=False
            )
            self.tokeniser.pad_token = self.tokeniser.eos_token
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
            self.model = AutoModelForCausalLM.from_pretrained(
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