
from src.qubit.prompting.injections import PromptInjection



def memory_module(memory_text: str):
    return PromptInjection(
        content=f"Recent memory:\n{memory_text}",
        priority=60
    )