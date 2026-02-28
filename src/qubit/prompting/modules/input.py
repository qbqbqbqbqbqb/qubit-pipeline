
from src.qubit.prompting.injections import PromptInjection



def input_module(user_input: str):
    return PromptInjection(
        content=f"{user_input}",
        priority=10
    )