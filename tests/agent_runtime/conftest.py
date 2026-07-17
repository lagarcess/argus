import pytest


@pytest.fixture(autouse=True)
def synthetic_market_data_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
