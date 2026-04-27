from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def test_gateway_limits_to_100_when_limit_is_none() -> None:
    client = MagicMock()
    gateway = SupabaseGateway(client=client)

    table = client.table.return_value
    select = table.select.return_value
    eq = select.eq.return_value
    eq.is_.return_value = eq
    ordered = eq.order.return_value
    ordered.order.return_value = ordered
    ordered.limit.return_value.execute.return_value.data = []

    gateway.list_conversations(user_id="user-1", limit=None)

    ordered.limit.assert_called_once_with(100)
