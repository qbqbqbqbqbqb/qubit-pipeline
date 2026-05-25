import pytest
from src.qubit.models.base_model_manager import BaseModelManager


def test_base_model_manager_is_abstract():
    with pytest.raises(TypeError):
        BaseModelManager()
