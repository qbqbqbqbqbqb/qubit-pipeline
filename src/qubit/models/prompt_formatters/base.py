"""PromptFormatter protocol for model-specific prompt preparation."""

from typing import Protocol, Optional, List, Dict, Any


class PromptFormatter(Protocol):
    """Protocol for turning high-level input into the exact string a specific model expects.

    Implementations encapsulate all model-specific formatting logic:
    - Chat templates (via tokenizer.apply_chat_template)
    - Role name mapping ("System" -> "system", custom tokens)
    - System prompt prepending / special placement
    - Reflection-specific wrappers, XML tags, etc.
    - Any other ritual required by a particular fine-tune

    The rest of the system (assemblers, reflection generators, cognitive layer)
    should produce either:
      - A list of {"role": str, "content": str} messages (preferred), or
      - An already-assembled text string + optional metadata

    Then hand the result to a formatter selected by the active LLMProfile.
    """

    def format(
        self,
        *,
        messages: Optional[List[Dict[str, str]]] = None,
        assembled_text: Optional[str] = None,
        system: Optional[str] = None,
        task: Optional[str] = None,
        tokenizer: Any = None,
        model_config: Any = None,
        **kwargs: Any,
    ) -> str:
        """Return the fully formatted prompt string ready for tokenization.

        Args:
            messages: Structured conversation (recommended). Roles should be
                normalized by the formatter (e.g. "system", "user", "assistant").
            assembled_text: Flat string from priority-based PromptAssembler
                (used for the main personality path during/after migration).
            system: Optional explicit system instruction to inject.
            task: Optional task hint (e.g. "reflection", "chat", "monologue").
            tokenizer: Tokenizer instance. Required by formatters that use
                apply_chat_template or need vocab for special tokens.
            model_config: The ModelConfig for the active profile (gives access
                to system_model_specific_prompt, extra_eos_tokens, etc.).
            **kwargs: Forward-compatible extension point.

        Returns:
            str: The exact text that should be passed to the model.
        """
        ...  # pragma: no cover
