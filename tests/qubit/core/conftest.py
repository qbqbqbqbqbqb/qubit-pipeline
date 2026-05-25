import pytest

# Core tests that touch create_app, services, or the runtime
# benefit from the shared heavy mocking stack.
pytestmark = [
    pytest.mark.usefixtures("mock_heavy_stack"),
]
