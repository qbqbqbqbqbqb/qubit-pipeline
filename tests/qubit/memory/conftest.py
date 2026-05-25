import pytest

# All tests in the memory directory are considered "heavy".
# They rely on the shared mock_heavy_stack fixture for isolation
# from chromadb, torch, transformers, etc.
pytestmark = [
    pytest.mark.heavy,
    pytest.mark.usefixtures("mock_heavy_stack"),
]
