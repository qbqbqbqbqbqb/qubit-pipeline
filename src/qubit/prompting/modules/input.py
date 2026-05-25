"""Prompt injection module for handling user input."""

from src.qubit.prompting.injections import PromptInjection

def input_module(user_input: str) -> PromptInjection:
    """
    Create a prompt injection from raw user input.

    This function wraps the user's input into a PromptInjection
    so it can be included in the final assembled prompt.

    Args:
        user_input (str): The raw input provided by the user.

    Returns:
        PromptInjection: A prompt injection containing the user input.
    """
    return PromptInjection(
        content=f"{user_input}",
        priority=10
    )
