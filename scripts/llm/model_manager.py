# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import torch

def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt') 
        nltk.download('punkt_tab')

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("ModelManager")

MODEL_NAME = "Sao10K/L3-8B-Stheno-v3.2"

class ModelManager:
    __instance = None
    def __new__(cls):
        if cls.__instance is None:
            instance = super().__new__(cls)
            try:
                instance._init()
                cls.__instance = instance
            except Exception:
                raise
        return cls.__instance
    
    def _init(self):
        download_nltk_data()
        # === Load model with transformers ===
        try:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16
            )

            self.tokenizer = AutoTokenizer.from_pretrained(
                MODEL_NAME,
                trust_remote_code=False
            )
            self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=False,
                dtype=torch.bfloat16
            )

            logger.info(f"[ModelManager] Loaded model: {MODEL_NAME} with 4-bit quantization")

        except Exception as e:
            logger.error(f"[init] Model initialisation failed: {e}")
            raise

    @classmethod
    def get_instance(cls):
        return cls()