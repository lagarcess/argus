from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_batched_fetch_helper_exists_for_unbounded_queries():
    gateway = SupabaseGateway(client=MagicMock())
    assert hasattr(gateway, "_fetch_all_rows")
