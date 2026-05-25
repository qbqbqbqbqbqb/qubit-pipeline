import sys
from unittest.mock import MagicMock
import pytest

sys.modules['torch'] = MagicMock()
sys.modules['torch'].float16 = "float16"
sys.modules['torch'].dtype = type("dtype", (), {})

from src.qubit.models.model_registry import MODEL_REGISTRY
from src.qubit.models.model_config import ModelConfig


def test_registry_contains_expected_models():
    assert "stheno" in MODEL_REGISTRY
    assert "gpt6" in MODEL_REGISTRY


def test_registry_values_are_model_configs():
    for key, config in MODEL_REGISTRY.items():
        assert isinstance(config, ModelConfig)
        assert config.model_name
