import pytest
from unittest.mock import MagicMock
import sys

# Pretend torch is installed so we can import the config without the real package
sys.modules['torch'] = MagicMock()
sys.modules['torch'].float16 = "float16"
sys.modules['torch'].dtype = type("dtype", (), {})

from src.qubit.models.model_config import GenerationConfig, ModelConfig


def test_generation_config_defaults():
    cfg = GenerationConfig()
    assert cfg.temperature == 0.9
    assert cfg.top_p == 0.9
    assert cfg.do_sample is True


def test_model_config_creation():
    cfg = ModelConfig(model_name="test/model")
    assert cfg.model_name == "test/model"
    assert isinstance(cfg.generation_config, GenerationConfig)
