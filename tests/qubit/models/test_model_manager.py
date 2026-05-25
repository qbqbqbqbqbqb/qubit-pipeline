import pytest
from unittest.mock import patch, MagicMock

pytest.importorskip("torch", reason="ModelManager requires torch + dotenv + HF")

try:
    import dotenv
except ImportError:
    pytest.skip("python-dotenv not installed", allow_module_level=True)

from src.qubit.models.model_manager import ModelManager


def test_model_manager_is_singleton():
    with patch("src.qubit.models.model_manager.HuggingFaceModelManager") as mock_hf:
        mock_hf.return_value = MagicMock()

        m1 = ModelManager()
        m2 = ModelManager()

        assert m1 is m2
