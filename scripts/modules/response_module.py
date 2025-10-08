import asyncio
from scripts.core.base_module import BaseModule
from scripts.utils.log_utils import get_logger
from scripts.managers.model_manager import ModelManager
from scripts.managers.queue_manager import QueueManager

from datetime import datetime, timezone

MAX_MESSAGE_AGE_SECONDS = 30 

class ResponseModule(BaseModule):
    def __init__(self, queue_manager: QueueManager, chat_sender, signals):
        super().__init__("ResponseModule", logger=get_logger("ResponseModule"))
        self.model = None
        self.tokeniser = None
        self.queue_manager = queue_manager
        self.chat_sender = chat_sender 
        self.model_manager = None
        self.signals = signals
        self._running = False

    async def start(self):
        self.logger.info("[start] Initialising ResponseModule...")
        self.model_manager = ModelManager.get_instance()
        self.model = self.model_manager.model
        self.tokeniser = self.model_manager.tokeniser
        await super().start()

    async def run(self):
        self.logger.info("[run] ResponseModule running.")
        self._running = True
        
        try:
            while self._running:
                self.logger.debug("[run] Waiting for next message from processing_queue...")
                msg = await self.queue_manager.processing_queue.get()
                self.logger.debug(f"[run] Retrieved message: {msg}")
                self.logger.debug(f"[run] Got message from processing_queue: {msg}")

                msg_type = msg.get("type")
                timestamp = msg.get("timestamp")

                if timestamp:
                    now = datetime.now()
                    age = (now - timestamp).total_seconds()
                    self.logger.debug(f"[run] Message age: {age:.1f}s")
                    if age > MAX_MESSAGE_AGE_SECONDS:
                        self.logger.info(f"[run] Dropping old message ({age:.1f}s): {msg}")
                        self.queue_manager.processing_queue.task_done()
                        continue

                if msg_type == "chat_message":
                    user = msg.get("user")
                    prompt = msg.get("prompt")
                    self.logger.info(f"[run] Processing chat message from {user}: {prompt}")

                    self.logger.debug("[run] Calling generate_response...")
                    response = await self.generate_response(prompt)
                    self.logger.info(f"[run] Generated response for {user}: {response}")

                    reply = f"@{user} {response}"
                    if self.chat_sender:
                        self.logger.debug("[run] Sending chat response...")
                        try:
                            await self.chat_sender(reply)
                        except Exception:
                            self.logger.exception("Failed to send chat reply")
                        else:
                            self.logger.info(f"[run] Sent chat response to {user}")

                elif msg_type == "monologue":
                    text = msg.get("text")
                    self.logger.info(f"[run] Processing monologue prompt: {text}")
                    self.logger.debug("[run] Calling generate_response for monologue...")
                    await self.generate_response(text)
                    self.logger.info("[run] Monologue response generated.")

                else:
                    self.logger.warning(f"[run] Unknown message type: {msg_type}")

                self.queue_manager.processing_queue.task_done()
                self.logger.debug("[run] Marked message done on processing_queue.")

        except asyncio.TimeoutError:
            self.logger.debug("[run] No message received in last 5 seconds, still waiting...")
        except asyncio.CancelledError:
            self.logger.info("[run] ResponseModule run cancelled.")
        except Exception as e:
            self.logger.exception(f"[run] Exception in run loop: {e}")
        finally:
            self.logger.info("[run] ResponseModule stopped.")



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
            'pad_token_id': self.model_manager.tokeniser.eos_token_id,
            'eos_token_id': [
                self.model_manager.tokeniser.eos_token_id,
                self.model_manager.tokeniser.convert_tokens_to_ids("<|eot_id|>"),
                self.model_manager.tokeniser.convert_tokens_to_ids("<|end_of_text|>")
            ] if "<|eot_id|>" in self.model_manager.tokeniser.get_vocab() else self.model_manager.tokeniser.eos_token_id
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
            self.logger.debug("[generate_text] Starting generation...")

            inputs = self.model_manager.tokeniser(
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

    async def apply_chat_template(self,
                                  chat: list,
                                  ) -> str:
        """
        Applies the Gemma 3 chat template to the provided chat messages.
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
        
    async def generate_response(self,
                                prompt,
                                max_new_tokens: int = 30
                                ) -> str:
        """
        Orchestrates the generation of a cleaned and constrained model response.
        """
        try:
            self.signals.ai_thinking = True

            if isinstance(prompt, str):
                chat_messages = [{"role": "user", "content": prompt}]
            else:
                chat_messages = prompt

            full_prompt = await self.apply_chat_template(chat=chat_messages)
            raw_output = await self.generate_text(full_prompt, max_new_tokens)

            self.logger.info(f"[generate_response] Final response: {raw_output}")

            if self.queue_manager and hasattr(self.queue_manager, "speech_queue"):
                try:
                    await self.queue_manager.enqueue_speech(raw_output, item_type="ai_response")
                except Exception as e:
                    self.logger.error(f"[generate_response] Failed to enqueue speech: {e}")

            return raw_output

        except Exception:
            self.logger.exception("[generate_response] Exception during generation")
            return "Something went wrong!"

        finally:
            self.signals.ai_thinking = False

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
            self.logger.warning(f"Text gen timed out after {timeout}")
            return "Timed out"
        except Exception as e:
            self.logger.exception(f"Failed generating text: {e}")
            return "Something went wrong!"

    def set_chat_sender(self, sender_callable):
        self.chat_sender = sender_callable
        self.logger.info("[set_chat_sender] Chat sender has been set.")

    async def _generate_response_with_retries(self, prompt) -> str:
        """
        Generate AI response with error handling and retries.

        Attempts to generate a monologue response using the AI response generator.
        Falls back to a generic error message if generation fails.

        Args:
            prompt: The formatted prompt for monologue generation

        Returns:
            Generated monologue text or fallback error message
        """
        try:
            response = await self.response_generator.generate_response_safely(prompt)
            return response
        except Exception as e:
            self.logger.exception(f"Error in generate response with retries: {e}")
            return "Something went wrong!"
