"""Formatter that delegates to the tokenizer's built-in chat template when available."""

from typing import Optional, List, Dict, Any

from src.qubit.models.prompt_formatters.base import PromptFormatter
from src.qubit.models.prompt_formatters.registry import register_formatter


class ChatTemplateFormatter:
    """Uses tokenizer.apply_chat_template when possible.

    This is the preferred path for any model that ships with a proper
    chat template (Llama-3, Mistral, Command-R, Qwen, etc.).

    Falls back to a reasonable default if no tokenizer or no template is present.
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
        # Normalize messages if we only got assembled_text
        if messages is None and assembled_text is not None:
            # Treat the whole thing as a single user turn for template purposes
            messages = [{"role": "user", "content": assembled_text}]

        if messages is None:
            messages = []

        # Optionally inject/override system message
        if system:
            # Prepend or replace first system message
            if messages and messages[0].get("role", "").lower() == "system":
                messages[0]["content"] = system
            else:
                messages = [{"role": "system", "content": system}] + messages

        # Try the real chat template
        if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                # Fall through to naive formatting on any template error
                pass

        # Naive fallback (role: content)
        parts = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages]
        return "\n".join(parts)


register_formatter("chat_template", ChatTemplateFormatter)
register_formatter("chatml", ChatTemplateFormatter)  # common alias
