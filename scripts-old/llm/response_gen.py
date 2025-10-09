import asyncio

from typing import Optional

# === Setup colorlog logger ===
from scripts.utils.log_utils import get_logger
logger = get_logger("ResponseGen")

from scripts.llm.model_manager import ModelManager
from scripts.io.text_processor import TextProcessor

class ResponseGen:
    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager.get_instance()
        self.text_processor = TextProcessor()

    def get_generation_config(self, max_tokens: int):
        """
        Returns generation configuration parameters.
        """
        return {
            'temperature': 1.17,  
            'top_p': 0.9, 
            'top_k': 50,
            'max_new_tokens': max_tokens,
            'repetition_penalty': 1.1,
            'do_sample': True,
            'pad_token_id': self.model_manager.tokenizer.eos_token_id,
            'eos_token_id': [
                self.model_manager.tokenizer.eos_token_id,
                self.model_manager.tokenizer.convert_tokens_to_ids("<|eot_id|>"),
                self.model_manager.tokenizer.convert_tokens_to_ids("<|end_of_text|>")
            ] if "<|eot_id|>" in self.model_manager.tokenizer.get_vocab() else self.model_manager.tokenizer.eos_token_id
        }

    async def generate_text(self,
                            prompt: str,
                            max_tokens: int,
                            timeout: float = 60.0
                            ) -> str:
        """
        Performs the text generation call using transformers.
        """
        try:
            logger.debug("[generate_text] Starting generation...")

            inputs = self.model_manager.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self.model_manager.model.device)

            loop = asyncio.get_running_loop()
            gen_config = self.get_generation_config(max_tokens)

            outputs = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.model_manager.model.generate(
                        **inputs,
                        **gen_config
                    )
                ),
                timeout
            )

            generated_text = self.model_manager.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()

            logger.debug("[generate_text] Generation completed...")
            logger.debug(f"[generate_text] Raw output: {generated_text[:60]}...")
            return generated_text

        except asyncio.TimeoutError:
            logger.warning(f"Text gen timed out after {timeout}")
            return "Timed out"
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
                                  chat: list,
                                  ) -> str:
        """
        Applies the Gemma 3 chat template to the provided chat messages.
        """
        try:
            return self.model_manager.tokenizer.apply_chat_template(
                chat,
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception as e:
            logger.error(f"Error applying chat template: {e}")
            raise
        
    async def generate_response(self,
                                prompt,
                                max_new_tokens: int = 30
                                ) -> str:
        """
        Orchestrates the generation of a cleaned and constrained model response.
        """
        try:
            #logger.info(f"[generate_response] Prompt received: {str(prompt)[:60]}...")

            if isinstance(prompt, str):
                chat_messages = [{"role": "user", "content": prompt}]
            else:
                chat_messages = prompt

            full_prompt = await self.apply_chat_template(chat=chat_messages)

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
            output = await self.generate_response(prompt, max_new_tokens)
            return output
        
        except asyncio.TimeoutError:
            logger.warning(f"Text gen timed out after {timeout}")
            return "Timed out"
        except Exception as e:
            logger.exception(f"Failed generating text: {e}")
            return "Something went wrong!"
