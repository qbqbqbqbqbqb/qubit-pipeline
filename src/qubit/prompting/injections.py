"""Data structures for prompt injection handling."""

from dataclasses import dataclass

@dataclass
class PromptInjection:
    """
    Represent a prompt injection segment for LLM input construction.

    Each injection contains content and an associated priority that
    determines its position in the final assembled prompt. Higher
    priority injections appear earlier in the prompt.

    Attributes:
        content (str): The text content of the injection.
        priority (int): Ordering priority (higher values come first).
    """
    content: str
    priority: int = 0
