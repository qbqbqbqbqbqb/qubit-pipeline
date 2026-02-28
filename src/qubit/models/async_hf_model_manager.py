import asyncio
from src.qubit.models.hf_model_manager import HuggingFaceModelManager

class AsyncHuggingFaceLLM:
    def __init__(self, model_manager: HuggingFaceModelManager, max_tokens=150):
        self.model_manager = model_manager
        self.max_tokens = max_tokens

    async def generate_response(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.model_manager.generate_dialogue(prompt, max_new_tokens=self.max_tokens)
        )