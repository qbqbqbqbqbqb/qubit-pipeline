"""Formatter tailored for reflection / internal reasoning tasks.

Can be used with the same model as main chat (different sampling + framing)
or with an entirely different model registered under the "reflection" profile.
"""

from typing import Optional, List, Dict, Any

from src.qubit.models.prompt_formatters.role_mapped import RoleMappedFormatter
from src.qubit.models.prompt_formatters.registry import register_formatter


class ReflectionFormatter(RoleMappedFormatter):
    """Adds light reflection-specific framing on top of role mapping.

    Currently just ensures a clear system instruction for analytical work.
    Can be extended with chain-of-thought wrappers, output format enforcement, etc.
    """

    REFLECTION_SYSTEM = (
        "You are an analytical AI that extracts high-value, generalizable insights "
        "from conversations. Focus on patterns, key facts, and memorable details. "
        "Be concise and structured."
    )

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
        # Force a strong analytical system prompt for reflection tasks
        effective_system = system or self.REFLECTION_SYSTEM

        return super().format(
            messages=messages,
            assembled_text=assembled_text,
            system=effective_system,
            task=task or "reflection",
            tokenizer=tokenizer,
            model_config=model_config,
            **kwargs,
        )


register_formatter("reflection", ReflectionFormatter)
register_formatter("reflection_role_mapped", ReflectionFormatter)
