"""Prompt injection module for incorporating recent chat history."""

from typing import Optional
from src.qubit.prompting.injections import PromptInjection


def chat_memory_module(recent_history: list) -> Optional[PromptInjection]:
    """
    Create a prompt injection from recent chat history.

    This function formats the last messages from the conversation
    into a prompt segment so the model can maintain context.

    Args:
        recent_history (list): A list of chat messages, where each item
            is expected to contain 'role' and 'content' keys.

    Returns:
        Optional[PromptInjection]: A prompt injection containing formatted
        chat history, or None if no history is available.
    """
    if not recent_history:
        return None

    history_str = "\n".join(
        [f"{item['role']}: {item['content']}" for item in recent_history[-10:]]
    )
    memory_text = f"Chat History:\n{history_str}" if history_str else ""

    return PromptInjection(
        content=memory_text,
        priority=70,
    )