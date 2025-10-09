import asyncio
import itertools
from scripts2.modules.base_module import BaseModule
from scripts2.managers.model_manager import ModelManager
from scripts2.config.config import ( MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION, 
                                    MAX_GENERATION_ATTEMPTS,
                                    INSTRUCTIONS_FILE)
from scripts2.managers.prompt_manager import PromptManager

class ResponseGeneratorModule(BaseModule):
    def __init__(self, signals, event_broker, model_manager=ModelManager, response_generation_enabled = True):
        super().__init__(name="ResponseGeneratorModule")
        self.signals = signals
        self.event_broker = event_broker
        self.model_manager = model_manager
        self.response_generation_enabled = response_generation_enabled
        self.prompt_manager = PromptManager(system_instructions=INSTRUCTIONS_FILE)
        
        self.counter = itertools.count()
        self.queue = asyncio.PriorityQueue()
        self.loop = None
        
        self._get_calls = 0
        self._task_done_calls = 0

    async def start(self):
        if not self.response_generation_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.model_manager = ModelManager.get_instance()
        self.model = self.model_manager.model
        self.tokeniser = self.model_manager.tokeniser

        self.loop = asyncio.get_running_loop()

        await super().start()

    async def run(self):
        while self._running:
            try:
                priority, count, event = await self.queue.get()
                await self.process_prompt(event)
                self.queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing prompt: {e}")

    async def process_prompt(self, event_data):
        text = event_data["text"]
        response = await self._generate_response_with_retries(text)

        self.event_broker.publish_event({
            "type": "response_generated",
            "response": response,
            "original_prompt": event_data.get("text") or event_data.get("message") or event_data,
            "original_type": event_data.get("type", "unknown"),
            "original_full": event_data,
        })

        self.logger.info(f"Generated response: {response}")
    
    def submit_prompt(self, event_data, priority=10):
        count = next(self.counter)
        asyncio.run_coroutine_threadsafe(
            self.queue.put((priority, count, event_data)), 
            self.loop)

    async def _generate_response(self, raw_prompt, max_new_tokens: int = MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION):
        try:
            if isinstance(raw_prompt, str):
                prompt = [{"role": "user", "content": raw_prompt}]
            else:
                prompt = raw_prompt

            prompt_with_system_prompt = self.prompt_manager.build_prompt(prompt)
            #self.logger.info(f"prompt before template {prompt_with_system_prompt}")
            full_prompt = await self._apply_chat_template(chat=prompt_with_system_prompt)
            #self.logger.info(f"prompt after template {full_prompt}")
            output = await self._generate_text(full_prompt, max_new_tokens)  
            
            return output
        except Exception:
            self.logger.exception("[generate_response] Exception during generation")
            return "Something went wrong!"
        finally:
            self.signals.ai_thinking = False

    def _get_generation_config(self, max_tokens: int):
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
            'pad_token_id': self.model_manager.tokeniser.eos_token_id,
            'eos_token_id': [
                self.model_manager.tokeniser.eos_token_id,
                self.model_manager.tokeniser.convert_tokens_to_ids("<|eot_id|>"),
                self.model_manager.tokeniser.convert_tokens_to_ids("<|end_of_text|>")
            ] if "<|eot_id|>" in self.model_manager.tokeniser.get_vocab() else self.model_manager.tokeniser.eos_token_id
        }

    async def _generate_text(self,
                            prompt: str,
                            max_tokens: int,
                            timeout: float = 60.0
                            ) -> str:
        """
        Performs the text generation call using transformers.
        """
        try:
            self.logger.debug("[generate_text] Starting generation...")

            inputs = self.model_manager.tokeniser(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=2048
            ).to(self.model_manager.model.device)

            loop = asyncio.get_running_loop()
            gen_config = self._get_generation_config(max_tokens)

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

            generated_text = self.model_manager.tokeniser.decode(
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
        
    async def _generate_response_with_retries(self, prompt, max_generation_attempts: int = MAX_GENERATION_ATTEMPTS) -> str:
        """
        Generate AI response with error handling and retries.

        Args:
            prompt: The formatted prompt for monologue generation.

        Returns:
            Generated monologue text or fallback error message after retries.
        """
        for attempt in range(1, max_generation_attempts + 1):
            try:
                response = await self._generate_response(prompt)
                return response 
            except Exception as e:
                self.logger.exception(f"[Attempt {attempt}/{max_generation_attempts}] Error generating response: {e}")
                if attempt == max_generation_attempts:
                    return "Something went wrong!"
                
    async def _apply_chat_template(self,
                                  chat: list,
                                  ) -> str:
        """
        i dont remember why i added this initially but i cant get my advanced prompts to work without it
        """
        try:
            return self.model_manager.tokeniser.apply_chat_template(
                chat,
                tokenize=False,
                add_generation_prompt=True
            )
        except Exception as e:
            self.logger.error(f"Error applying chat template: {e}")
            raise
