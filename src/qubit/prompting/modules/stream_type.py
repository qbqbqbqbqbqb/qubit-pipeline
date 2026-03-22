"""Prompt injection module for defining stream type context."""

from src.qubit.prompting.injections import PromptInjection

def stream_type_module() -> PromptInjection:
    """
    Create a prompt injection describing the stream type.

    This injection informs the language model about the current
    stream context (e.g., "Just Chatting") so responses can be
    aligned with the intended format or tone.

    Returns:
        PromptInjection: The configured prompt injection with
        stream type context.
    """
    STREAM_TYPE = "Just Chatting"
    # TODO: move stream type into config
    content = (
        f"You are doing a {STREAM_TYPE} stream."
    )

    return PromptInjection(
        content=content,
        priority=80
    )