"""Build local Auth proof gateways through the production dependency factory."""

import os
from unittest.mock import patch

from argus.domain.supabase_gateway import SupabaseGateway


def local_supabase_gateway() -> SupabaseGateway:
    # Keep the local disposable credentials scoped to construction. The production
    # factory supplies all persistent readers, including saved-message freshness.
    with patch.dict(
        os.environ,
        {
            "SUPABASE_URL": os.environ["ARGUS_LOCAL_SUPABASE_URL"],
            "SUPABASE_SERVICE_ROLE_KEY": os.environ["ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY"],
            "SUPABASE_ANON_KEY": os.environ["ARGUS_LOCAL_SUPABASE_ANON_KEY"],
            "DATABASE_URL": os.environ["ARGUS_DISPOSABLE_DATABASE_URL"],
        },
    ):
        return SupabaseGateway.from_env()
