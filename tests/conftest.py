import pytest
from argus.api.main import app


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides don't leak between tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
