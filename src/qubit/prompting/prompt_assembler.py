"""Utilities for assembling prompts from multiple injections."""

from typing import Any
from src.qubit.prompting.injections import PromptInjection, USER_INPUT_PRIORITY

class PromptAssembler:
    """
    Assemble a final prompt by combining multiple PromptInjection objects.

    Injections can be added with different priorities, which determine
    their order in the final constructed prompt.
    """

    def __init__(self: Any):
        """
        Initialize an empty PromptAssembler.

        Attributes:
            injections (list[PromptInjection]): Stored prompt injections.
        """
        self.injections = []

    def add(self: Any, injection: PromptInjection) -> None:
        """
        Add a prompt injection to the assembler.

        Args:
            injection (PromptInjection): The injection to add.

        Returns:
            None
        """
        self.injections.append(injection)

    def build_parts(self: Any) -> tuple[str, str]:
        """
        Split the assembled prompt into (system_text, user_text).

        Injections with priority > USER_INPUT_PRIORITY are concatenated into
        the system message. Injections at or below USER_INPUT_PRIORITY form
        the user turn. This is used by chat-template formatters so the model
        receives a properly structured conversation rather than a flat string.

        Returns:
            tuple[str, str]: (system_text, user_text). Either may be empty
            if no injections fall into that category.
        """
        sorted_injections = sorted(
            self.injections,
            key=lambda x: x.priority,
            reverse=True,
        )
        system_parts = [inj.content for inj in sorted_injections if inj.priority > USER_INPUT_PRIORITY]
        user_parts = [inj.content for inj in sorted_injections if inj.priority <= USER_INPUT_PRIORITY]
        return "\n\n".join(system_parts), "\n\n".join(user_parts)

    def build(self: Any) -> str:
        """
        Build the final prompt string.

        The injections are sorted by priority (highest first) and then
        concatenated with double newlines between each segment.

        Returns:
            str: The assembled prompt.
        """
        sorted_injections = sorted(
            self.injections,
            key=lambda x: x.priority,
            reverse=True
        )

        return "\n\n".join(inj.content for inj in sorted_injections)
