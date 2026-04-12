import pytest
from argus.api.main import app
from argus.config import (
    get_crypto_data_client,
    get_settings,
    get_stock_data_client,
    get_supabase_client,
    get_supabase_service_client,
    get_trading_client,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all lru_caches before each test to ensure environment isolation."""
    get_settings.cache_clear()
    get_stock_data_client.cache_clear()
    get_crypto_data_client.cache_clear()
    get_supabase_client.cache_clear()
    get_supabase_service_client.cache_clear()
    get_trading_client.cache_clear()


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides don't leak between tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
