
from dataclasses import dataclass

"""
Represents a prompt injection that can be added to the prompt before sending to the LLM.
The priority field can be used to control the order of injections (higher priority first).
"""

@dataclass
class PromptInjection:
    content: str
    priority: int = 0