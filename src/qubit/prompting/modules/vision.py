"""Prompt injection module for current screen/window vision context."""

from src.qubit.prompting.injections import PromptInjection


def vision_module(description: str | None) -> PromptInjection | None:
    """
    Returns a PromptInjection with the latest vision description, or None
    if vision is off or no description is available yet.
    Priority 45 — injected after chat history, before the input message.
    """
    if not description:
        return None

    return PromptInjection(
        content=f"What you can currently see on screen: {description}",
        priority=45,
    )