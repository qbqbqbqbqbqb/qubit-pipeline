"""Model manager singleton.

This module provides the ModelManager class, which is responsible for
initialising and managing a single instance of a HuggingFaceModelManager.
It loads configuration from environment variables and ensures that only
one model instance is created during runtime.
"""

import os
from dotenv import load_dotenv
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.qubit.models.model_registry import MODEL_REGISTRY


class ModelManager:
    """Singleton wrapper for managing a Hugging Face model instance.

    This class ensures that only one instance of HuggingFaceModelManager
    is created. It handles environment configuration, model selection,
    and optional LoRA adapter validation during initialisation.
    """
    _instance = None

    def __new__(cls):
        """Create or return the singleton instance.

        This method initialises the model on first access by:
        - Validating the LoRA adapter path
        - Loading environment variables
        - Selecting the active model configuration
        - Instantiating the HuggingFaceModelManager

        Returns:
            ModelManager: The singleton instance wrapping the model manager.
        """
        if cls._instance is None:

            lora_path = "training_data/training/qubit-lora-final"

            if not os.path.exists(lora_path):
                print(f"LoRA folder does not exist: {lora_path}")
            else:
                print(f"LoRA folder exists: {lora_path}")

            adapter_file = os.path.join(lora_path, "adapter_config.json")
            if os.path.isfile(adapter_file):
                print("LoRA config found:", adapter_file)
            else:
                print("LoRA config missing! Cannot load LoRA.")

            load_dotenv()
            model_key = os.getenv("ACTIVE_MODEL", "stheno")
            print("ACTIVE_MODEL:", os.getenv("ACTIVE_MODEL"))


            config = MODEL_REGISTRY[model_key]

            cls._instance = HuggingFaceModelManager(config)

            if getattr(cls._instance.model, "is_loaded_in_4bit", False):
                print(f"Model loaded in 4-bit: {config.load_in_4bit}")
            if hasattr(cls._instance.model, "peft_config") and cls._instance.model.peft_config is not None:
                print(f"LoRA adapter loaded from: {config.lora_path}")
            else:
                print("No LoRA adapter loaded")

        return cls._instance

    @classmethod
    def get_instance(cls):
        """Get the singleton model manager instance.

        Returns:
            ModelManager: The singleton instance of the model manager.
        """
        return cls()
