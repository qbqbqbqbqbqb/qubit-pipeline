from dotenv import load_dotenv
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.qubit.models.model_registry import MODEL_REGISTRY
import os


class ModelManager:
    _instance = None

    def __new__(cls):
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
        return cls()