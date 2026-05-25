"""Core system prompt module for defining base AI behavior."""

from src.qubit.prompting.injections import PromptInjection
from config.config import CORE_SYSTEM_PROMPT


def core_system_module() -> PromptInjection:
    """
    Create the core system prompt injection.

    This defines the base behavior, identity, and constraints of the AI,
    including tone adaptation, response length, and safety rules.

    Returns:
        PromptInjection: The highest-priority system-level prompt injection.
    """
    content = CORE_SYSTEM_PROMPT

    return PromptInjection(
        content=content,
        priority=100,
    )