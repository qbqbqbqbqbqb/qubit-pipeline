# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

from vllm import LLM, SamplingParams

from transformers import AutoProcessor

def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt') 
        nltk.download('punkt_tab')

# === Setup colorlog logger ===
from scripts.io.log_utils import get_logger
logger = get_logger("ModelManager")

MODEL_NAME = "RedHatAI/gemma-3-4b-it-quantized.w4a16"

class ModelManager:
    __instance = None
    def __new__(cls):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
            cls.__instance._init()
        return cls.__instance
    
    def _init(self):
        download_nltk_data()
        # === Load LLAMA2 model ===
        try:
            self.processor = AutoProcessor.from_pretrained(
                MODEL_NAME, 
                trust_remote_code=False
            )
            self.llm = LLM(
                model=MODEL_NAME, 
                trust_remote_code=False,
                tensor_parallel_size = 1,
                gpu_memory_utilization=0.9,
                #max_model_len=4096
            )

            logger.info(f"[Dialogue_Model_Utils] Loaded model: {MODEL_NAME}")

        except Exception as e:
            logger.error(f"[init] Model initialisation failed.")

    @classmethod
    def get_instance(cls):
        return cls()