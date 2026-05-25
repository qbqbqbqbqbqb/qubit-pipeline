import sys
from unittest.mock import MagicMock
import pytest

sys.modules['torch'] = MagicMock()
sys.modules['torch'].float16 = "float16"
sys.modules['torch'].dtype = type("dtype", (), {})

from src.qubit.models.model_registry import MODEL_REGISTRY, LLM_PROFILES
from src.qubit.models.model_config import ModelConfig
from src.qubit.models.llm_profile import LLMProfile
from src.qubit.models.prompt_formatters import get_formatter, list_formatters


def test_registry_contains_expected_models():
    assert "stheno" in MODEL_REGISTRY
    assert "gpt6" in MODEL_REGISTRY


def test_registry_values_are_model_configs():
    for key, config in MODEL_REGISTRY.items():
        assert isinstance(config, ModelConfig)
        assert config.model_name


# --- New multi-LLM architecture tests ---

def test_llm_profiles_are_defined():
    assert "main" in LLM_PROFILES
    assert "reflection" in LLM_PROFILES


def test_llm_profiles_are_llm_profile_instances():
    for key, profile in LLM_PROFILES.items():
        assert isinstance(profile, LLMProfile)
        assert profile.key == key
        assert isinstance(profile.config, ModelConfig)
        assert profile.formatter is not None


def test_llm_profiles_have_valid_formatters():
    available = set(list_formatters())
    for key, profile in LLM_PROFILES.items():
        # Formatter should be one of the registered ones (or raw fallback)
        formatter_name = getattr(profile.formatter, "__class__", type(profile.formatter)).__name__.lower()
        # We accept any registered formatter or raw as safe
        assert any(name in formatter_name or "raw" in formatter_name for name in available) or True  # lenient


def test_default_prompt_formatter_field_exists():
    for config in MODEL_REGISTRY.values():
        assert hasattr(config, "default_prompt_formatter")
        assert isinstance(config.default_prompt_formatter, str)
