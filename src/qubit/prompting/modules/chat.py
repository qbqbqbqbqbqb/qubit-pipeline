
from src.qubit.prompting.injections import PromptInjection

def memory_module(chats: str):
    return PromptInjection(
        content=f"Recent chat history:\n{chats}",
        priority=60
    )