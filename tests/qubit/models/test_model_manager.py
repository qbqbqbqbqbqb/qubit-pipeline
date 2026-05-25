import pytest
from unittest.mock import patch, MagicMock


def test_model_manager_is_singleton():
    # Lazy import so collection of this test file never requires torch etc.
    from src.qubit.models.model_manager import ModelManager

    with patch("src.qubit.models.model_manager.HuggingFaceModelManager") as mock_hf:
        mock_hf.return_value = MagicMock()

        m1 = ModelManager()
        m2 = ModelManager()

        assert m1 is m2
