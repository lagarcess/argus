from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_no_unbounded_fetches_when_limit_is_none():
    gateway = SupabaseGateway(client=MagicMock())
    assert not hasattr(gateway, "_fetch_all_rows")
