"""Formatter that supports explicit system prompts and normalizes roles.

Useful for older fine-tunes (Pygmalion, MythoMax, etc.) that do not use
modern chat templates but expect a specific system line + role markers.
"""

from typing import Optional, List, Dict, Any

from src.qubit.models.prompt_formatters.base import PromptFormatter
from src.qubit.models.prompt_formatters.registry import register_formatter


class RoleMappedFormatter:
    """Applies a system prompt (from model_config or explicit) and normalizes roles.

    Role mapping can be customized per subclass or via constructor.
    """

    def __init__(self, role_map: Optional[Dict[str, str]] = None):
        # Default mapping: make common variants consistent
        self.role_map = role_map or {
            "system": "System",
            "user": "User",
            "assistant": "Assistant",
            "human": "User",
            "ai": "Assistant",
            "bot": "Assistant",
        }

    def _map_role(self, role: str) -> str:
        lower = role.lower()
        return self.role_map.get(lower, role)

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
        effective_system = system

        # Pull model-specific system prompt if present and no explicit one given
        if effective_system is None and model_config is not None:
            effective_system = getattr(model_config, "system_model_specific_prompt", None)

        # Build or normalize messages
        if messages is None:
            if assembled_text is not None:
                messages = [{"role": "user", "content": assembled_text}]
            else:
                messages = []

        # Inject system if we have one and messages don't already start with system
        if effective_system:
            if not messages or self._map_role(messages[0].get("role", "")).lower() != "system":
                messages = [{"role": "system", "content": effective_system}] + messages

        # Format with mapped roles
        parts = []
        for m in messages:
            role = self._map_role(m.get("role", "user"))
            content = m.get("content", "")
            parts.append(f"{role}: {content}")

        return "\n".join(parts)


# Common registrations for classic fine-tunes
register_formatter("role_mapped", RoleMappedFormatter)
register_formatter("pygmalion", RoleMappedFormatter)  # the gpt6 entry can use this
register_formatter("prepend_system", RoleMappedFormatter)
