"""Prompt injection module for incorporating reflection memory."""

from typing import Optional
from src.qubit.prompting.injections import PromptInjection

def reflection_memory_module(recent_reflections: list) -> Optional[PromptInjection]:
    """
    Create a prompt injection from recent reflection memory.

    This function formats a list of recent reflections into a single
    prompt segment that can be included in the LLM input. If no
    reflections are provided, no injection is created.

    Args:
        recent_reflections (list): A list of reflection items, where each
            item is expected to contain a 'content' key with text.

    Returns:
        Optional[PromptInjection]: A prompt injection containing formatted
        reflections, or None if no reflections are available.
    """
    if not recent_reflections:
        return None

    reflections_str = "\n".join([item['content'] for item in recent_reflections])

    memory_text = f"Recent reflections:\n{reflections_str}" if reflections_str else ""

    return PromptInjection(
        content=memory_text,
        priority=60
    )
