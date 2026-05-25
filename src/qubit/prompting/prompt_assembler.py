"""Utilities for assembling prompts from multiple injections."""

from typing import Any
from src.qubit.prompting.injections import PromptInjection

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
