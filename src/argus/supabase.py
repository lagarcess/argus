"""
Shared Supabase client initialization for Argus.
"""

from loguru import logger
from supabase import Client, create_client

from argus.config import get_settings

_settings = get_settings()
SUPABASE_URL = _settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = _settings.SUPABASE_SERVICE_ROLE_KEY

supabase_client: Client | None = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
else:
    logger.warning("Supabase credentials missing. Some features may be disabled.")


def get_supabase_client() -> Client | None:
    """Get the shared Supabase client instance."""
    return supabase_client
