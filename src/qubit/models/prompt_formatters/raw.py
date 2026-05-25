"""Raw / pass-through formatter (safe default during migration)."""

from typing import Optional, List, Dict, Any

from src.qubit.models.prompt_formatters.base import PromptFormatter
from src.qubit.models.prompt_formatters.registry import register_formatter


class RawStringFormatter:
    """The simplest formatter: returns input as-is or does minimal joining.

    Used as the default when no special formatting is required, or during
    the transition period while higher layers still produce flat strings.
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
        if assembled_text is not None:
            if system:
                return f"{system}\n\n{assembled_text}"
            return assembled_text

        if messages:
            # Very naive role: content join — good enough for raw fallback
            parts = []
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                parts.append(f"{role}: {content}")
            text = "\n".join(parts)
            if system:
                text = f"{system}\n\n{text}"
            return text

        # Last resort
        return system or ""


# Self-register under the most common names for "no special treatment"
register_formatter("raw", RawStringFormatter)
register_formatter("default", RawStringFormatter)
