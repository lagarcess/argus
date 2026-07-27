import os

import pytest

PROVIDER_CREDENTIAL_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "PERPLEXITY_API_KEY",
)


@pytest.fixture(autouse=True)
def mock_auth_env(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "true")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "true")
    monkeypatch.setenv("ARGUS_CONTEXT_PACKETS_ENABLED", "false")
    # Synthetic market data is the default; live paths opt in per test.
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")


@pytest.fixture(autouse=True)
def blank_provider_credentials(monkeypatch):
    """Suite runs stay provider-free unless a live eval is explicitly requested.

    Values are emptied rather than deleted: `load_project_dotenv()` uses
    `override=False`, which refills an absent variable from a worktree `.env`.
    """
    if os.getenv("ARGUS_RUN_LIVE_EVALS") == "1":
        return
    for name in PROVIDER_CREDENTIAL_ENV_VARS:
        monkeypatch.setenv(name, "")
