import asyncio
from src.qubit.models.hf_model_manager import HuggingFaceModelManager
from src.utils.log_utils import get_logger

logger = get_logger(__name__)

class AsyncHuggingFaceLLM:
    def __init__(self, model_manager: HuggingFaceModelManager, max_tokens=150):
        self.model_manager = model_manager
        self.max_tokens = max_tokens

    async def generate_response(self, prompt: str) -> str:
        """Generate a response safely with thread executor and full logging."""
        loop = asyncio.get_running_loop()
        logger.info(f"[AsyncHuggingFaceLLM] Generating response, prompt length={len(prompt)}")

        try:
            # run in executor to avoid blocking the event loop
            response = await loop.run_in_executor(
                None,
                lambda: self._safe_generate(prompt)
            )
            if not response or not response.strip():
                logger.warning("[AsyncHuggingFaceLLM] Received empty response")
                return "Sorry, I couldn't generate a response right now."
            return response
        except Exception as e:
            logger.error(f"[AsyncHuggingFaceLLM] Exception during response generation: {e}")
            return "Sorry, I couldn't generate a response right now."

    def _safe_generate(self, prompt: str) -> str:
        """Wrap the actual model call to catch synchronous exceptions."""
        try:
            return self.model_manager.generate_dialogue(prompt, max_new_tokens=self.max_tokens)
        except Exception as e:
            logger.error(f"[AsyncHuggingFaceLLM] Model generation error: {e}")
            return ""