import asyncio
import re
from typing import Optional
import torch


# === Setup colorlog logger ===
from log_utils import get_logger
logger = get_logger("ResponseGen")

from model_manager import ModelManager
from text_processor import TextProcessor

import os
os.environ["VLLM_LOGGING_LEVEL"] = "DEBUG"

from vllm import SamplingParams, LLM

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
            repetition_penalty=1.2,
        )

    async def generate_text(self, 
                            prompt: str, 
                            max_tokens: int,
                            timeout: float = 60.0
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
                logger.debug("[generate_text] samplings params done...")
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
                                max_new_tokens: int = 30
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
        max_new_tokens: int =30,
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
