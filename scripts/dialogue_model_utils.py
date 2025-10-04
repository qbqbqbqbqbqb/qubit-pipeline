import asyncio
import re
from typing import Optional
import torch
from vllm import LLM, SamplingParams
from transformers import AutoProcessor

# === Setup sentence tokenisation ===
import nltk
from nltk.tokenize import sent_tokenize

def download_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt') 
        nltk.download('punkt_tab')

# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("Dialogue_Model_Utils")

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
                gpu_memory_utilization=0.9
            )

            logger.info(f"[Dialogue_Model_Utils] Loaded model: {MODEL_NAME}")

        except Exception as e:
            logger.error(f"[init] Model initialisation failed.")

    @classmethod
    def get_instance(cls):
        return cls()

# === Utility Functions ===
class TextProcessor:
    @staticmethod
    def trim_to_last_sentence(text: str) -> str:
        """
        Returns text trimmed to the last full sentence according to the sentence tokeniser.
        """
        sentences = sent_tokenize(text)
        if not sentences:
            return ""
        if not text.endswith(('.', '!', '?')):
            sentences = sentences[:-1]
        return ' '.join(sentences).strip()

    @staticmethod
    def limit_sentences(text: str, max_sentences: int=3) -> str:
        """
        Limits text to a maximum number of sentences using the sentence tokeniser.
        """
        sentences = sent_tokenize(text)
        return ' '.join(sentences[:max_sentences]).strip()

    @staticmethod
    def limit_chars(text: str, max_chars: int=300) -> str:
        """
        Truncates the input text to a maximum character length without cutting off words abruptly.
        """
        if len(text) > max_chars:
            return text[:max_chars].rsplit(' ', 1)[0] + '...'
        return text

    @staticmethod
    def clean_and_limit_text(text: str, 
                             max_sentences: int=3, 
                             max_chars: int=300) -> str:
        """
        Cleans and limits the input text by trimming to full sentences, limiting sentence count, and truncating characters.
        """
        text = TextProcessor.trim_to_last_sentence(text)
        text = TextProcessor.limit_sentences(text, max_sentences)
        text = TextProcessor.limit_chars(text, max_chars)
        return text

    @staticmethod
    def contains_url(text: str) -> bool:
        """
        Checks if the input text contains a URL pattern.
        """
        url_pattern = re.compile(r'https?://\S+|www\.\S+|.com\S*', re.IGNORECASE)
        return bool(url_pattern.search(text))

    @staticmethod
    def clean_generated_text(text: str) -> str:
        """
        Cleans generated text by removing text consisting only of punctuation and stripping trailing punctuation,
        and removes sentences containing URLs.
        """
        if re.fullmatch(r"[:;,.!?\-]+", text.strip()):
            return ""
        text = text.strip().strip(":;,.!?-")
        sentences = text.split('. ')
        sentences = [s for s in sentences if not contains_url(s)]
        return '. '.join(sentences).strip()

class ResponseGen:
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager.get_instance()
        self.text_processor = TextProcessor()

    def get_sampling_params(self, max_tokens: int) -> SamplingParams:
        """
        Configures and returns sampling parameters for generation.
        """
        return SamplingParams(
            temperature=1.1,
            top_p=0.9,
            top_k=80,
            max_tokens=max_tokens,
            bad_words=["http", "https", "www", ".com", ".net", ".org", ".io", ".gov", ".edu"],
            repetition_penalty=1.2,
        )

    async def generate_text(self, 
                            prompt: str, 
                            max_tokens: int,
                            timeout: float = 120.0
                            ) -> str:
        """
        Performs the text generation call using the LLM.
        """
        try:
            logger.debug("[generate_text] Starting generation...")
            loop = asyncio.get_running_loop()

            async def gen():
                inputs = {"prompt": prompt, "multi_modal_data": {}}
                sampling_params = self.get_sampling_params(max_tokens)
                outputs = await loop.run_in_executor(
                    None,
                    self.model_manager.llm.generate,
                    inputs,
                    sampling_params
                )
                return outputs[0].outputs[0].text.strip()
            
            text = await asyncio.wait_for(gen(), timeout)
            logger.debug(f"[generate_text] Raw output: {text[:60]}...")
            return text
        except asyncio.TimeoutError:
            logger.warning(f"Text gen timed out after {timeout}")
            return "Timed otu"
        except Exception as e:
            logger.warning(f"Failed generating text. {e}")
            return "Something went wrong!"

    async def clean_response(self,
                             text: str, 
                             fallback: str = "Sorry, I couldn't generate a response.",
                             max_sentences: int=3,
                             max_chars: int = 300
                            ) -> str:
        """
        Cleans, limits, and safely returns the final response.
        """
        cleaned = self.text_processor.clean_and_limit_text(
            text=text, 
            max_sentences=max_sentences, 
            max_chars=max_chars)
        return cleaned if cleaned.strip() else fallback

    async def apply_chat_template(self, 
                                  chat: dict,
                                  ) -> dict:
        """
        Applies the Gemma 3 chat template to the provided chat dictionary.
        """
        return self.model_manager.processor.apply_chat_template(chat, add_generation_prompt=True)
        
    async def generate_response(self, 
                                prompt: str, 
                                max_new_tokens: int = 100
                                ) -> str:
        """
        Orchestrates the generation of a cleaned and constrained model response.
        """
        try:
            #logger.info(f"[generate_response] Prompt received: {prompt[:60]}...")
            
            full_prompt = await self.apply_chat_template(chat=prompt)
            
            raw_output = await self.generate_text(full_prompt, max_new_tokens)
            final_response = await self.clean_response(raw_output)

            logger.info(f"[generate_response] Final response: {final_response}")
            return final_response

        except Exception:
            logger.exception("[generate_response] Exception during generation")
            return "Something went wrong!"
        
    async def generate_response_safely(
        self,
        prompt: dict,
        max_new_tokens: int = 100,
        timeout: float = 15.0
    ) -> str:
        try:
            # Directly await the generate_response method
            output = await self.generate_response(prompt, max_new_tokens)
            return output
        
        except asyncio.TimeoutError:
            logger.warning(f"Text gen timed out after {timeout}")
            return "Timed out"
        except Exception as e:
            logger.exception(f"Failed generating text: {e}")
            return "Something went wrong!"
