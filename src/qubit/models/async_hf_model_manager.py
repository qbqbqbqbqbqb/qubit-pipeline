"""Asynchronous Hugging Face language model wrapper.

This module provides AsyncHuggingFaceLLM, a wrapper around a synchronous
HuggingFaceModelManager that enables non-blocking text generation using
asyncio and thread execution.
"""

import asyncio
from typing import Any
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.utils.log_utils import get_logger

logger = get_logger(__name__)


class AsyncHuggingFaceLLM:
    """Async wrapper for Hugging Face model inference.

    This class enables asynchronous response generation by delegating
    blocking model calls to a thread executor, ensuring compatibility
    with async event loops.

    Attributes:
        model_manager (HuggingFaceModelManager): Underlying model manager.
        max_tokens (int): Maximum number of tokens to generate per request.
    """

    def __init__(self: Any, model_manager: HuggingFaceModelManager, max_tokens: int=150):
        """Initialise the async model wrapper.

        Args:
            model_manager (HuggingFaceModelManager): Model manager instance.
            max_tokens (int, optional): Maximum tokens to generate.
                Defaults to 150.
        """
        self.model_manager = model_manager
        self.max_tokens = max_tokens

    async def generate_response(self, prompt: str) -> str:
        """Generate a response asynchronously from a prompt.

        This method runs the synchronous model inference in a thread
        executor to avoid blocking the event loop. It also includes
        logging and error handling for robustness.

        Args:
            prompt (str): Input text prompt.

        Returns:
            str: Generated response, or a fallback message if generation fails.
        """
        loop = asyncio.get_running_loop()
        logger.info("[AsyncHuggingFaceLLM] Generating response, prompt length=%s", len(prompt))

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self._safe_generate(prompt)
            )
            if not response or not response.strip():
                logger.warning("[AsyncHuggingFaceLLM] Received empty response")
                return "Sorry, I couldn't generate a response right now."
            return response
        except Exception as e:
            logger.error("[AsyncHuggingFaceLLM] Exception during response generation: {%s}", e)
            return "Sorry, I couldn't generate a response right now."

    def _safe_generate(self, prompt: str) -> str:
        """Safely execute the synchronous model generation call.

        This method wraps the model_manager.generate_dialogue call
        to catch and log exceptions without propagating them.

        Args:
            prompt (str): Input text prompt.

        Returns:
            str: Generated response, or an empty string if an error occurs.
        """
        try:
            return self.model_manager.generate_dialogue(
                prompt,
                max_new_tokens=self.max_tokens
            )
        except Exception as e:
            logger.error("[AsyncHuggingFaceLLM] Model generation error: %s", e)
            return ""
