import asyncio
import datetime
import itertools
import os
from scripts2.modules.base_module import BaseModule
from scripts2.models.model_manager import ModelManager
from scripts2.config.config import ( MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION,
                                    MAX_GENERATION_ATTEMPTS,
                                    SPELLING_DICTIONARY_FILE, BLACKLISTED_WORDS_LIST, WHITELISTED_WORDS_LIST)
from scripts2.managers.prompt_manager import PromptManager
from scripts2.utils.dialogue_generation_utils import is_valid_response, normalise_response, remove_bot_name, convert_to_british_english

"""
This module provides the ResponseGeneratorModule class for generating AI responses to user prompts.

It handles asynchronous response generation using a language model, including prompt building, text generation,
response validation, normalization, and conversion to British English spelling.
"""

class ResponseGeneratorModule(BaseModule):
    """
    ResponseGeneratorModule is responsible for generating AI responses in a dialogue system.

    It uses an event-driven architecture to process prompts asynchronously, with priority queuing and retry mechanisms.
    The module integrates with model and prompt managers to build and generate responses, applying various filters and transformations.
    """
    def __init__(self, signals, event_broker, model_manager=ModelManager, prompt_manager:PromptManager = None, response_generation_enabled = True):
        """
        Initializes the ResponseGeneratorModule.

        Args:
            signals: A signals object for synchronization.
            event_broker: The central event broker for publishing events.
            model_manager: The ModelManager class or instance for language model access.
            prompt_manager: Optional PromptManager instance for building prompts.
            response_generation_enabled: Flag to enable or disable response generation.
        """
        super().__init__(name="ResponseGeneratorModule")
        self.signals = signals
        self.event_broker = event_broker
        self.model_manager = model_manager
        self.response_generation_enabled = response_generation_enabled
        self.prompt_manager = prompt_manager
        
        self.counter = itertools.count()
        self.queue = asyncio.PriorityQueue()
        self.loop = None
        
    async def start(self):
        """
        Starts the ResponseGeneratorModule.

        Initializes the model manager, assigns the event loop, and signals readiness.
        If response generation is disabled, it logs and returns without starting.
        """
        if not self.response_generation_enabled:
            self.logger.info(f"[start] {self.name} is disabled. Not starting.")
            return
        self.model_manager = ModelManager.get_instance()
        self._model = self.model_manager.model
        self.tokeniser = self.model_manager.tokenizer

        from peft import PeftModel

        if isinstance(self._model, PeftModel):
            print("LoRA adapter attached:", self._model.active_adapter)
            print("LoRA weights in model:", any('lora' in n.lower() for n, _ in self._model.named_parameters()))
        else:
            print("No LoRA adapter loaded")

        self.loop = asyncio.get_running_loop()
        self.logger.info(f"Assigned event loop: {self.loop}")

        await super().start()
        self.signals.response_generator_ready.set()

    async def run(self):
        """
        Main asynchronous loop for processing prompts.

        Continuously retrieves prompts from the priority queue and processes them.
        Handles exceptions during processing.
        """
        while self._running:
            try:
                priority, count, event = await self.queue.get()
                await self.process_prompt(event)
                self.queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing prompt: {e}")

    async def process_prompt(self, event_data):
        """
        Processes a single prompt event to generate and publish a response.

        Generates a response with retries, validates it, applies transformations, and publishes the result via the event broker.

        Args:
            event_data (dict): The event data containing the prompt text and user information.
        """
        text = event_data["text"]
        user_id = event_data.get("user")
        original_type = event_data.get("original_type")
        response = await self._generate_response_with_retries(raw_prompt=text, user_id=user_id, original_type=original_type)

        is_valid, filtered_response = is_valid_response(response=response, blacklist=BLACKLISTED_WORDS_LIST, whitelist=WHITELISTED_WORDS_LIST)
        if not is_valid:
            self.logger.warning("[run] Invalid response, skipping.")
            await asyncio.sleep(1)
        else:
            response_without_intro = remove_bot_name(filtered_response)
            # not sure whether its best to implement this or not? it can cut off some sentences that would make sense without it
            normalised_response = normalise_response(response_without_intro)
            british_response = convert_to_british_english(normalised_response, SPELLING_DICTIONARY_FILE)
            self.event_broker.publish_event({
                "type": "response_generated",
                "response": british_response,
                "original_prompt": event_data.get("text") or event_data.get("message") or event_data,
                "original_type": event_data.get("type", "unknown"),
                "original_full": event_data,
            })

            self.logger.info(f"Generated response: {british_response}")
    
    def submit_prompt(self, event_data, priority=5):
        """
        Submits a prompt to the processing queue with a given priority.

        Uses run_coroutine_threadsafe to add the prompt to the asyncio queue.

        Args:
            event_data (dict): The event data for the prompt.
            priority (int): The priority level for the prompt (default 5).
        """
        if self.loop is None:
            self.logger.warning(f"submit_prompt called but loop is None. Ignoring prompt: {event_data}")
            return
        self.logger.info(f"ResponseGenerator received prompt: {event_data} with priority {priority}")
        count = next(self.counter)
        asyncio.run_coroutine_threadsafe(
            self.queue.put((priority, count, event_data)),
            self.loop)


        

    async def _generate_response(self, raw_prompt, 
                                 max_new_tokens: int = MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION, 
                                 use_system_prompt=True, 
                                 user_id=None,
                                 original_type = None):
        """
        Generates a response to the given prompt using the language model.

        Builds the prompt if needed, applies chat template, generates text, and returns the output.

        Args:
            raw_prompt (str): The raw user prompt.
            max_new_tokens (int): Maximum new tokens to generate.
            use_system_prompt (bool): Whether to use system prompt building.
            user_id: Optional user identifier for prompt building.

        Returns:
            str: The generated response text.
        """

        try:
            self.signals.ai_thinking.set()

            if use_system_prompt:
                prompt = self.prompt_manager.build_prompt(
                    raw_prompt, user_id=user_id, original_type=original_type
                )
            else:
                prompt = raw_prompt

            prompt = self.model_manager.prepare_prompt(prompt)

            loop = asyncio.get_running_loop()
            output = await loop.run_in_executor(
                None,
                self.model_manager.generate_dialogue,
                prompt,
                max_new_tokens
            )

            return output

        except Exception:
            self.logger.exception("[generate_response] Exception during generation")
            return "Something went wrong!"
        
        finally:
            self.signals.ai_thinking.clear()
        
    async def _generate_response_with_retries(self, raw_prompt, 
                                              max_generation_attempts: int = MAX_GENERATION_ATTEMPTS, 
                                              use_system_prompt=True, 
                                              max_new_tokens=MAX_NEW_TOKENS_FOR_DIALOGUE_GENERATION, 
                                              user_id=None, original_type=None) -> str:
        """
        Generate AI response with error handling and retries.

        Args:
            prompt: The formatted prompt for monologue generation.

        Returns:
            Generated monologue text or fallback error message after retries.
        """
        for attempt in range(1, max_generation_attempts + 1):
            try:
                response = await self._generate_response(raw_prompt, use_system_prompt=use_system_prompt, user_id=user_id, original_type=original_type)
                return response
            except Exception as e:
                self.logger.exception(f"[Attempt {attempt}/{max_generation_attempts}] Error generating response: {e}")
                if attempt == max_generation_attempts:
                    return "Something went wrong!"
                

    async def stop(self):
        """
        Stops the ResponseGeneratorModule.

        Calls the parent stop method to clean up resources.
        """
        await super().stop()
