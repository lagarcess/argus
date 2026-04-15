from argus.config import Settings


def test_supabase_alias_resolution_from_canonical_values():
    settings = Settings(
        _env_file=None,
        AGENT_MODEL="openrouter/model-primary",
        AGENT_FALLBACK_MODEL="openrouter/model-fallback",
        SUPABASE_PROJECT_URL="https://example.supabase.co",
        SUPABASE_ANON_PUBLIC_KEY="anon-public-key",
        SUPABASE_URL="${SUPABASE_PROJECT_URL}",
        SUPABASE_ANON_KEY="${SUPABASE_ANON_PUBLIC_KEY}",
        NEXT_PUBLIC_SUPABASE_URL="${SUPABASE_PROJECT_URL}",
        NEXT_PUBLIC_SUPABASE_ANON_KEY="${SUPABASE_ANON_PUBLIC_KEY}",
    )

    assert settings.SUPABASE_URL == "https://example.supabase.co"
    assert settings.SUPABASE_ANON_KEY == "anon-public-key"
    assert settings.NEXT_PUBLIC_SUPABASE_URL == "https://example.supabase.co"
    assert settings.NEXT_PUBLIC_SUPABASE_ANON_KEY == "anon-public-key"
