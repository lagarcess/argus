from argus.config import get_settings
from pydantic import ValidationError


def test_get_settings_is_cached_singleton(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "development")

    first = get_settings()
    second = get_settings()

    assert first is second


def test_get_settings_loads_environment_values(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("SUPABASE_PROJECT_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_PUBLIC_KEY", "anon-key")

    settings = get_settings()

    assert settings.APP_ENV == "production"
    assert settings.SUPABASE_URL == "https://example.supabase.co"
    assert settings.SUPABASE_ANON_KEY == "anon-key"


def test_get_settings_rejects_invalid_app_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "staging")

    try:
        get_settings()
        raise AssertionError("Expected ValidationError for invalid APP_ENV")
    except ValidationError as exc:
        assert "APP_ENV must be one of" in str(exc)
    finally:
        get_settings.cache_clear()
