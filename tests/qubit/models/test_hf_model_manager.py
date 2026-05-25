import pytest
from unittest.mock import patch, MagicMock


def test_hf_model_manager_instantiation_requires_config():
    # Lazy import — collection succeeds even without torch/transformers.
    from src.qubit.models.hf_model_manager import HuggingFaceModelManager
    from src.qubit.models.model_config import ModelConfig

    with patch("src.qubit.models.hf_model_manager.HuggingFaceModelManager._load") as mock_load:
        cfg = ModelConfig(model_name="test-model")
        mgr = HuggingFaceModelManager(config=cfg)

        assert mgr is not None
        assert mgr.config.model_name == "test-model"
        mock_load.assert_called_once()  # proves we avoided real model loading
