# === Setup sentence tokenisation ===
import time
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
        return cls()