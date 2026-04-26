import pytest


@pytest.fixture(autouse=True)
def mock_auth_env(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "true")
