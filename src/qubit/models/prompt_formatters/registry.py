"""Registry of available PromptFormatter implementations."""

from typing import Dict, Type
from src.qubit.models.prompt_formatters.base import PromptFormatter

# Central registry. Keys are stable identifiers used in LLMProfile definitions.
FORMATTER_REGISTRY: Dict[str, Type[PromptFormatter]] = {}


def register_formatter(name: str, formatter_cls: Type[PromptFormatter]) -> None:
    """Register a formatter class under a stable name."""
    if name in FORMATTER_REGISTRY:
        raise ValueError(f"Formatter '{name}' is already registered")
    FORMATTER_REGISTRY[name] = formatter_cls


def get_formatter(name: str) -> PromptFormatter:
    """Instantiate and return a formatter by registered name.

    Falls back to RawStringFormatter if the name is unknown (safe default).
    """
    if name not in FORMATTER_REGISTRY:
        # Lazy import to avoid circulars
        from src.qubit.models.prompt_formatters.raw import RawStringFormatter
        return RawStringFormatter()
    return FORMATTER_REGISTRY[name]()


def list_formatters() -> list[str]:
    return list(FORMATTER_REGISTRY.keys())
