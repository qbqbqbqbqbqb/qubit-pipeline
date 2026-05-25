import pytest

# All tests in the models directory are considered "heavy".
# They rely on the shared mock_heavy_stack fixture for isolation.
pytestmark = [
    pytest.mark.heavy,
    pytest.mark.usefixtures("mock_heavy_stack"),
]

# Suppress the "unknown mark" warning when this conftest is loaded early
pytest.register_assert_rewrite("tests.qubit.models")
