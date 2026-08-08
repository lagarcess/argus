import os

import pytest

PROVIDER_CREDENTIAL_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "PERPLEXITY_API_KEY",
)


def _live_evals_requested() -> bool:
    return os.getenv("ARGUS_RUN_LIVE_EVALS") == "1"


@pytest.fixture(autouse=True)
def mock_auth_env(monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "true")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "true")
    monkeypatch.setenv("ARGUS_CONTEXT_PACKETS_ENABLED", "false")


@pytest.fixture(autouse=True)
def reset_guest_funnel_milestones():
    """Milestone claims are durable by design, so they must not leak between
    tests the way they must not leak between requests."""
    from argus.api import state as api_state

    api_state.store.guest_funnel_milestones.clear()
    yield
    api_state.store.guest_funnel_milestones.clear()


@pytest.fixture(autouse=True)
def provider_free_env(monkeypatch):
    """Suite runs stay provider-free unless a live eval is explicitly requested.

    Sanctioned live runs own their own provider mode and credentials, including
    the mode `ARGUS_EVAL_ENV_FILE` supplies, so this fixture must not touch
    either. Credentials are emptied rather than deleted: `load_project_dotenv()`
    uses `override=False`, which refills an absent variable from a worktree
    `.env`.
    """
    if _live_evals_requested():
        return
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    for name in PROVIDER_CREDENTIAL_ENV_VARS:
        monkeypatch.setenv(name, "")
