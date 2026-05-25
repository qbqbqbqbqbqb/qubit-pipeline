"""Prompt formatters package.

This package contains all model-specific prompt preparation logic.

The key export is PromptFormatter (protocol) and the registry helpers.
Concrete implementations live in their own modules and self-register.
"""

from src.qubit.models.prompt_formatters.base import PromptFormatter
from src.qubit.models.prompt_formatters.registry import (
    FORMATTER_REGISTRY,
    register_formatter,
    get_formatter,
    list_formatters,
)

# Import concrete implementations so they self-register on package load
from src.qubit.models.prompt_formatters import raw          # noqa: F401
from src.qubit.models.prompt_formatters import chat_template  # noqa: F401
from src.qubit.models.prompt_formatters import role_mapped    # noqa: F401
from src.qubit.models.prompt_formatters import reflection     # noqa: F401

__all__ = [
    "PromptFormatter",
    "FORMATTER_REGISTRY",
    "register_formatter",
    "get_formatter",
    "list_formatters",
]
