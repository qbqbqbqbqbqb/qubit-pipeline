"""Prompt injection module for defining stream type context."""

from src.qubit.prompting.injections import PromptInjection
from config.settings import STREAM_TYPE


def stream_type_module(stream_type: str | None = None) -> PromptInjection:
    """
    Create a prompt injection describing the current stream type.
    Accepts an optional stream_type override from RuntimeState so the value
    can be changed at runtime from the frontend. Falls back to the settings
    default if not provided.
    """
    active_type = stream_type or STREAM_TYPE
    return PromptInjection(
        content=f"You are doing a {active_type} stream.",
        priority=80,
    )