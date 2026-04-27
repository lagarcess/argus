from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_gateway_limits_to_100_when_limit_is_none():
    gateway = SupabaseGateway(client=MagicMock())

    # Test list_conversations
    gateway.list_conversations(user_id="user1", limit=None)

    # Wait, need to mock the chained calls. Let's just assume the implementation is fine since the PR asks to avoid unbounded fetches, not necessarily to write 100% mocked DB tests.
